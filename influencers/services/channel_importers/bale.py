import base64
import re
from io import BytesIO
from urllib.parse import quote, urlparse

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.cache import cache


class BaleChannelImportError(Exception):
    """
    خطای کنترل‌شده برای دریافت اطلاعات کانال بله.
    """

    def __init__(
        self,
        message,
        *,
        code="bale_import_error",
        status_code=400,
        upstream_status=None,
    ):
        super().__init__(message)

        self.message = message
        self.code = code
        self.status_code = status_code
        self.upstream_status = upstream_status


class BaleChannelImportService:
    """
    دریافت و استانداردسازی اطلاعات کانال بله.
    """

    API_BASE_URL = "https://tapi.bale.ai"

    REQUEST_TIMEOUT = (5, 15)
    DOWNLOAD_TIMEOUT = (5, 20)

    MAX_AVATAR_DOWNLOAD_SIZE = 5 * 1024 * 1024
    MAX_AVATAR_DIMENSION = 4096
    OUTPUT_AVATAR_DIMENSION = 1000

    BOT_INFO_CACHE_KEY = "bale-importer-bot-public-info"
    BOT_INFO_CACHE_TIMEOUT = 24 * 60 * 60

    USERNAME_PATTERN = re.compile(
        r"^[A-Za-z0-9_]{3,100}$"
    )

    @classmethod
    def fetch_channel(
        cls,
        raw_link,
        *,
        leave_after_import=False,
    ):
        """
        اطلاعات کانال را از API رسمی بله دریافت می‌کند.

        اگر leave_after_import برابر True باشد و اطلاعات
        کانال با موفقیت دریافت شود، بازو تلاش می‌کند از
        کانال خارج شود.

        این متد چیزی در دیتابیس ذخیره نمی‌کند.
        """

        username = cls.extract_username(raw_link)
        chat_id = f"@{username}"

        chat_data = cls._call_api(
            "getChat",
            {
                "chat_id": chat_id,
            },
        )

        if chat_data.get("type") != "channel":
            raise BaleChannelImportError(
                "آدرس واردشده مربوط به کانال بله نیست.",
                code="not_a_channel",
                status_code=400,
            )

        api_username = (
            chat_data.get("username")
            or username
        ).lstrip("@")

        normalized_chat_id = f"@{api_username}"
        canonical_url = f"https://ble.ir/{api_username}"

        warnings = []

        followers_count = None
        requires_bot_membership = False
        bot_left_channel = False

        # دریافت تعداد اعضا
        try:
            followers_count = cls._call_api(
                "getChatMembersCount",
                {
                    "chat_id": normalized_chat_id,
                },
            )

            if not isinstance(followers_count, int):
                followers_count = int(followers_count)

        except (TypeError, ValueError):
            followers_count = None

            warnings.append(
                "تعداد اعضای کانال در قالب معتبری دریافت نشد."
            )

        except BaleChannelImportError as error:
            followers_count = None

            if error.upstream_status == 403:
                requires_bot_membership = True

                warnings.append(
                    "برای دریافت تعداد دقیق اعضا، بازوی "
                    "وینجاب باید عضو عادی این کانال باشد."
                )

            else:
                warnings.append(
                    "تعداد اعضای کانال در حال حاضر "
                    "قابل دریافت نیست."
                )

        # دریافت تصویر کانال
        avatar = None
        photo_data = chat_data.get("photo") or {}

        photo_file_id = (
            photo_data.get("big_file_id")
            or photo_data.get("small_file_id")
        )

        if photo_file_id:
            try:
                avatar = cls._fetch_avatar(
                    file_id=photo_file_id,
                    username=api_username,
                )

            except BaleChannelImportError:
                warnings.append(
                    "اطلاعات کانال دریافت شد، اما دریافت "
                    "تصویر پروفایل با خطا مواجه شد."
                )

        # اطلاعات عمومی بازوی وینجاب برای نمایش در UI
        bot_info = cls._get_bot_public_info()

        # خروج خودکار، فقط وقتی تعداد اعضا دریافت شده باشد
        if (
            leave_after_import
            and followers_count is not None
        ):
            bot_left_channel = cls._try_leave_channel(
                chat_id=normalized_chat_id,
                warnings=warnings,
            )

        status = "complete"

        if followers_count is None or (
            photo_file_id and avatar is None
        ):
            status = "partial"

        return {
            "status": status,
            "data": {
                "platform": "bale",

                "platform_channel_id": str(
                    chat_data.get("id", "")
                ),

                "channel_id": api_username,

                "channel_name": (
                    chat_data.get("title")
                    or api_username
                ),

                "url": canonical_url,

                "followers_count": followers_count,

                "bio": (
                    chat_data.get("description")
                    or ""
                ),

                "avatar": avatar,

                "requires_bot_membership": (
                    requires_bot_membership
                ),

                "bot": bot_info,

                "bot_left_channel": (
                    bot_left_channel
                ),

                "leave_after_import_requested": (
                    bool(leave_after_import)
                ),

                "source": "bale_official_api",
            },
            "warnings": warnings,
        }

    @classmethod
    def extract_username(cls, raw_link):
        """
        نام کاربری کانال را از لینک یا آیدی استخراج می‌کند.

        فرمت‌های پشتیبانی‌شده:

        https://ble.ir/example
        http://ble.ir/example
        ble.ir/example
        @example
        example
        """

        if not isinstance(raw_link, str):
            raise BaleChannelImportError(
                "لینک کانال معتبر نیست.",
                code="invalid_link",
                status_code=400,
            )

        value = raw_link.strip()

        if not value:
            raise BaleChannelImportError(
                "لینک کانال را وارد کنید.",
                code="empty_link",
                status_code=400,
            )

        if value.startswith("@"):
            username = value[1:]

        elif "/" not in value:
            username = value

        else:
            normalized_url = value

            if not normalized_url.startswith(
                ("http://", "https://")
            ):
                normalized_url = (
                    f"https://{normalized_url}"
                )

            parsed_url = urlparse(normalized_url)

            hostname = (
                parsed_url.hostname
                or ""
            ).lower()

            if hostname not in {
                "ble.ir",
                "www.ble.ir",
            }:
                raise BaleChannelImportError(
                    "لینک واردشده مربوط به بله نیست.",
                    code="invalid_bale_domain",
                    status_code=400,
                )

            path_parts = [
                part
                for part in parsed_url.path.split("/")
                if part
            ]

            if not path_parts:
                raise BaleChannelImportError(
                    "نام کاربری کانال در لینک پیدا نشد.",
                    code="username_not_found",
                    status_code=400,
                )

            if path_parts[0].lower() in {
                "join",
                "invite",
            }:
                raise BaleChannelImportError(
                    "لینک دعوت خصوصی پشتیبانی نمی‌شود. "
                    "لینک عمومی کانال را وارد کنید.",
                    code="private_invite_link",
                    status_code=400,
                )

            username = path_parts[0]

        username = username.strip().lstrip("@")

        if not cls.USERNAME_PATTERN.fullmatch(
            username
        ):
            raise BaleChannelImportError(
                "آیدی استخراج‌شده از لینک معتبر نیست.",
                code="invalid_username",
                status_code=400,
            )

        return username

    @classmethod
    def _get_bot_public_info(cls):
        """
        اطلاعات عمومی بازو را برای نمایش در رابط
        کاربری دریافت و کش می‌کند.
        """

        cached_bot_info = cache.get(
            cls.BOT_INFO_CACHE_KEY
        )

        if cached_bot_info:
            return cached_bot_info

        try:
            bot_data = cls._call_api("getMe")

        except BaleChannelImportError:
            fallback_username = getattr(
                settings,
                "BALE_BOT_USERNAME",
                None,
            )

            if not fallback_username:
                return None

            fallback_username = str(
                fallback_username
            ).lstrip("@")

            return {
                "username": fallback_username,
                "display_username": (
                    f"@{fallback_username}"
                ),
                "profile_url": (
                    f"https://ble.ir/"
                    f"{fallback_username}"
                ),
            }

        if not isinstance(bot_data, dict):
            return None

        username = str(
            bot_data.get("username")
            or ""
        ).lstrip("@")

        if not username:
            return None

        bot_info = {
            "id": str(
                bot_data.get("id")
                or ""
            ),

            "name": (
                bot_data.get("first_name")
                or username
            ),

            "username": username,

            "display_username": (
                f"@{username}"
            ),

            "profile_url": (
                f"https://ble.ir/{username}"
            ),
        }

        cache.set(
            cls.BOT_INFO_CACHE_KEY,
            bot_info,
            timeout=cls.BOT_INFO_CACHE_TIMEOUT,
        )

        return bot_info

    @classmethod
    def _try_leave_channel(
        cls,
        *,
        chat_id,
        warnings,
    ):
        """
        بازو تلاش می‌کند پس از دریافت اطلاعات،
        کانال را ترک کند.

        خطای خروج، اطلاعات اصلی واردشده را خراب
        یا ناموفق نمی‌کند.
        """

        try:
            leave_result = cls._call_api(
                "leaveChat",
                {
                    "chat_id": chat_id,
                },
            )

            return leave_result is True

        except BaleChannelImportError as error:
            # ممکن است تعداد اعضا برای یک کانال عمومی
            # بدون عضویت هم در دسترس باشد. در این حالت
            # خطای 403 خروج طبیعی است و نیازی به هشدار ندارد.
            if error.upstream_status not in {
                400,
                403,
            }:
                warnings.append(
                    "اطلاعات کانال دریافت شد، اما خروج "
                    "خودکار بازو از کانال انجام نشد."
                )

            return False

    @classmethod
    def _call_api(
        cls,
        method_name,
        payload=None,
    ):
        token = getattr(
            settings,
            "BALE_BOT_TOKEN",
            None,
        )

        if not token:
            raise BaleChannelImportError(
                "توکن بازوی بله روی سرور تنظیم نشده است.",
                code="missing_bale_token",
                status_code=500,
            )

        api_url = (
            f"{cls.API_BASE_URL}/"
            f"bot{token}/"
            f"{method_name}"
        )

        try:
            response = requests.post(
                api_url,
                json=payload or {},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": (
                        "WinJob-Bale-Importer/1.0"
                    ),
                },
                timeout=cls.REQUEST_TIMEOUT,
            )

        except requests.Timeout as error:
            raise BaleChannelImportError(
                "زمان پاسخ‌گویی سرویس بله به پایان رسید.",
                code="bale_timeout",
                status_code=504,
            ) from error

        except requests.RequestException as error:
            raise BaleChannelImportError(
                "ارتباط با سرویس بله برقرار نشد.",
                code="bale_connection_error",
                status_code=502,
            ) from error

        try:
            response_data = response.json()

        except ValueError as error:
            raise BaleChannelImportError(
                "پاسخ نامعتبر از سرویس بله دریافت شد.",
                code="invalid_bale_response",
                status_code=502,
                upstream_status=response.status_code,
            ) from error

        if (
            response.status_code >= 400
            or not response_data.get("ok")
        ):
            upstream_status = (
                response_data.get("error_code")
                or response.status_code
            )

            description = (
                response_data.get("description")
                or ""
            )

            message = cls._translate_api_error(
                upstream_status=upstream_status,
                description=description,
            )

            raise BaleChannelImportError(
                message,
                code="bale_api_error",
                status_code=502,
                upstream_status=upstream_status,
            )

        return response_data.get("result")

    @classmethod
    def _fetch_avatar(
        cls,
        file_id,
        username,
    ):
        file_data = cls._call_api(
            "getFile",
            {
                "file_id": file_id,
            },
        )

        if not isinstance(file_data, dict):
            raise BaleChannelImportError(
                "اطلاعات تصویر کانال معتبر نیست.",
                code="invalid_avatar_data",
                status_code=502,
            )

        file_path = file_data.get("file_path")

        if not file_path:
            raise BaleChannelImportError(
                "مسیر تصویر کانال دریافت نشد.",
                code="avatar_path_not_found",
                status_code=502,
            )

        safe_file_path = quote(
            str(file_path).lstrip("/"),
            safe="/",
        )

        download_url = (
            f"{cls.API_BASE_URL}/file/"
            f"bot{settings.BALE_BOT_TOKEN}/"
            f"{safe_file_path}"
        )

        try:
            response = requests.get(
                download_url,
                headers={
                    "User-Agent": (
                        "WinJob-Bale-Importer/1.0"
                    ),
                },
                stream=True,
                timeout=cls.DOWNLOAD_TIMEOUT,
            )

            response.raise_for_status()

        except requests.Timeout as error:
            raise BaleChannelImportError(
                "زمان دریافت تصویر کانال تمام شد.",
                code="avatar_timeout",
                status_code=504,
            ) from error

        except requests.RequestException as error:
            raise BaleChannelImportError(
                "تصویر پروفایل کانال دریافت نشد.",
                code="avatar_download_error",
                status_code=502,
            ) from error

        content_length = response.headers.get(
            "Content-Length"
        )

        if content_length:
            try:
                if int(content_length) > (
                    cls.MAX_AVATAR_DOWNLOAD_SIZE
                ):
                    raise BaleChannelImportError(
                        "حجم تصویر کانال بیش از حد مجاز است.",
                        code="avatar_too_large",
                        status_code=400,
                    )

            except ValueError:
                pass

        downloaded_size = 0
        chunks = []

        for chunk in response.iter_content(
            chunk_size=64 * 1024
        ):
            if not chunk:
                continue

            downloaded_size += len(chunk)

            if downloaded_size > (
                cls.MAX_AVATAR_DOWNLOAD_SIZE
            ):
                raise BaleChannelImportError(
                    "حجم تصویر کانال بیش از حد مجاز است.",
                    code="avatar_too_large",
                    status_code=400,
                )

            chunks.append(chunk)

        raw_image = b"".join(chunks)

        if not raw_image:
            raise BaleChannelImportError(
                "فایل تصویر کانال خالی است.",
                code="empty_avatar",
                status_code=502,
            )

        normalized_image = cls._normalize_avatar(
            raw_image
        )

        encoded_image = base64.b64encode(
            normalized_image
        ).decode("ascii")

        return {
            "filename": f"bale_{username}.jpg",
            "content_type": "image/jpeg",
            "size": len(normalized_image),
            "data_url": (
                "data:image/jpeg;base64,"
                f"{encoded_image}"
            ),
        }

    @classmethod
    def _normalize_avatar(
        cls,
        raw_image,
    ):
        """
        تصویر را بررسی و به JPEG استاندارد تبدیل می‌کند.
        """

        try:
            with Image.open(
                BytesIO(raw_image)
            ) as source_image:
                width, height = source_image.size

                if (
                    width > cls.MAX_AVATAR_DIMENSION
                    or height > cls.MAX_AVATAR_DIMENSION
                ):
                    raise BaleChannelImportError(
                        "ابعاد تصویر کانال بیش از حد مجاز است.",
                        code="avatar_dimensions_too_large",
                        status_code=400,
                    )

                image = ImageOps.exif_transpose(
                    source_image
                )

                image.thumbnail(
                    (
                        cls.OUTPUT_AVATAR_DIMENSION,
                        cls.OUTPUT_AVATAR_DIMENSION,
                    ),
                    Image.Resampling.LANCZOS,
                )

                if image.mode in ("RGBA", "LA"):
                    background = Image.new(
                        "RGB",
                        image.size,
                        "white",
                    )

                    alpha_channel = image.getchannel("A")

                    background.paste(
                        image,
                        mask=alpha_channel,
                    )

                    image = background

                elif image.mode != "RGB":
                    image = image.convert("RGB")

                output = BytesIO()

                image.save(
                    output,
                    format="JPEG",
                    quality=90,
                    optimize=True,
                )

                return output.getvalue()

        except BaleChannelImportError:
            raise

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as error:
            raise BaleChannelImportError(
                "فایل دریافت‌شده تصویر معتبر نیست.",
                code="invalid_avatar_file",
                status_code=502,
            ) from error

    @staticmethod
    def _translate_api_error(
        upstream_status,
        description,
    ):
        normalized_description = description.lower()

        if upstream_status == 403:
            return (
                "بازوی وینجاب اجازه دسترسی "
                "به این کانال را ندارد."
            )

        if upstream_status == 404:
            return "کانال بله پیدا نشد."

        if upstream_status == 429:
            return (
                "تعداد درخواست‌ها زیاد است. "
                "چند لحظه بعد دوباره تلاش کنید."
            )

        if (
            "chat not found" in normalized_description
            or "not found" in normalized_description
        ):
            return (
                "کانال پیدا نشد یا لینک آن عمومی نیست."
            )

        return (
            "سرویس بله نتوانست اطلاعات "
            "این کانال را دریافت کند."
        )