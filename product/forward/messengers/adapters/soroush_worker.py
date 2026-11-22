"""ورکر ایزوله (Subprocess) برای اجرای عملیات asyncio/MTProto سروش‌پلاس بدون تداخل با Gevent و Django.

سروش‌پلاس در وین‌فوروارد به صورت سبک و سریع فقط برای ورود OTP، همگام‌سازی کانال‌ها (با دانلود آواتار از سرور مدیا)
و ارسال پیام متنی/کپشن استفاده می‌شود. اجرای این اسکریپت در پروسه مجزا از تداخل با GeventWorker جلوگیری می‌کند.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from typing import Any

_DEFAULT_MEDIA_ENDPOINT = ("185.60.137.28", 8443)


async def _get_media_dc_map(client) -> dict[int, tuple[str, int]]:
    """دریافت نقشه سرورهای اختصاصی مدیا (media_only=True) برای دانلود سریع آواتار کانال‌ها."""
    dc_map: dict[int, tuple[str, int]] = {}
    try:
        from splusthon.tl.functions.help import GetConfigRequest

        cfg = await client(GetConfigRequest())
        for opt in getattr(cfg, "dc_options", []):
            if getattr(opt, "media_only", False) and getattr(opt, "ip_address", None):
                dc_map[int(opt.id)] = (str(opt.ip_address), int(opt.port or 8443))
    except Exception:
        pass
    return dc_map


async def _download_channel_avatar(
    client,
    ent,
    dc_map: dict[int, tuple[str, int]],
    senders_cache: dict[tuple[str, int], Any],
) -> bytes:
    """دانلود سریع آواتار کانال از سرور مدیا (جلوگیری از خطای 422 روی سرور اتصال اصلی)."""
    from splusthon import utils
    from splusthon.network import MTProtoSender
    from splusthon.network.connection import ConnectionTcpObfuscated
    from splusthon.tl.functions.upload import GetFileRequest
    from splusthon.tl.types import ChatPhoto, InputPeerPhotoFileLocation

    photo = getattr(ent, "photo", None)
    if not isinstance(photo, ChatPhoto):
        return b""

    dc_id = int(getattr(photo, "dc_id", 0) or getattr(client.session, "dc_id", 1) or 1)
    endpoint = dc_map.get(dc_id) or next(iter(dc_map.values()), _DEFAULT_MEDIA_ENDPOINT)
    host, port = endpoint

    sender = senders_cache.get(endpoint)
    if sender is None:
        sender = MTProtoSender(client.session.auth_key, loggers=client._log)
        await sender.connect(
            ConnectionTcpObfuscated(
                host,
                port,
                dc_id=dc_id,
                loggers=client._log,
                proxy=None,
                local_addr=None,
            )
        )
        senders_cache[endpoint] = sender

    peer = utils.get_input_peer(ent, check_hash=False)
    loc = InputPeerPhotoFileLocation(peer=peer, photo_id=photo.photo_id, big=False)

    buf = bytearray()
    offset = 0
    limit = 64 * 1024
    while True:
        res = await sender.send(GetFileRequest(location=loc, offset=offset, limit=limit))
        chunk = getattr(res, "bytes", b"") or b""
        if not chunk:
            break
        buf.extend(chunk)
        if len(chunk) < limit:
            break
        offset += len(chunk)
        if offset >= 2 * 1024 * 1024:
            break
    return bytes(buf)


async def _resolve_channel_entity(client, chat_id: str, access_hash: str = ""):
    """یافتن InputEntity کانال با اولویت access_hash کش‌شده (ارسال فوری بدون iter_dialogs)."""
    raw = str(chat_id or "").strip()
    if not raw:
        raise ValueError("شناسه کانال سروش‌پلاس خالی است.")

    # ۱. مسیر فوق‌سریع برای کانال‌های خصوصی با access_hash ذخیره‌شده
    if access_hash and str(access_hash).lstrip("-").isdigit():
        clean_num = raw.lstrip("@")
        if clean_num.startswith("-100"):
            clean_num = clean_num[4:]
        clean_num = clean_num.lstrip("-")
        if clean_num.isdigit():
            try:
                from splusthon.tl.types import InputPeerChannel

                return InputPeerChannel(channel_id=int(clean_num), access_hash=int(access_hash))
            except Exception:
                pass

    candidates: list[Any] = []
    if raw.startswith("@"):
        candidates.append(raw)
    elif raw.lstrip("-").isdigit():
        num = int(raw)
        candidates.append(num)
        if num > 0:
            candidates.append(int(f"-100{num}"))
    else:
        candidates.append(f"@{raw}")
        candidates.append(raw)

    for cand in candidates:
        try:
            return await client.get_input_entity(cand)
        except Exception:
            continue

    target_digits = raw.lstrip("-@")
    async for dlg in client.iter_dialogs(limit=150):
        ent = getattr(dlg, "entity", None)
        if not ent:
            continue
        ent_id = str(getattr(ent, "id", ""))
        ent_uname = (getattr(ent, "username", "") or "").lower()
        if ent_id == target_digits or (ent_uname and ent_uname == target_digits.lower()):
            return await client.get_input_entity(ent)

    raise LookupError(f"CANNOT FIND ANY ENTITY: {chat_id}")


async def _execute(payload: dict) -> dict:
    from splusthon import SoroushClient
    from splusthon.sessions import StringSession

    action = payload.get("action")

    if action == "send_code":
        phone = payload["phone_number"]
        client = SoroushClient(StringSession())
        try:
            await client.connect()
            sent = await client.send_code_request(phone)
            return {
                "ok": True,
                "data": {
                    "phone_number": phone,
                    "phone_code_hash": sent.phone_code_hash,
                    "tmp_session": client.session.save(),
                },
            }
        finally:
            await client.disconnect()

    if action == "sign_in":
        phone = payload["phone_number"]
        code = payload["phone_code"]
        phone_code_hash = payload["phone_code_hash"]
        tmp_session = payload["tmp_session"]
        password = (payload.get("password") or "").strip()

        client = SoroushClient(StringSession(tmp_session))
        try:
            await client.connect()
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except Exception as err:
                err_up = str(err).upper()
                if "SESSION_PASSWORD_NEEDED" in err_up or "PASSWORD" in err_up:
                    if not password:
                        return {
                            "ok": False,
                            "error_kind": "permission",
                            "error": "این حساب دارای رمز تایید دو مرحله‌ای است؛ لطفاً رمز دو مرحله‌ای را هم وارد کنید.",
                        }
                    await client.sign_in(password=password)
                else:
                    raise

            me = await client.get_me()
            return {
                "ok": True,
                "data": {
                    "string_session": client.session.save(),
                    "user": {
                        "id": str(getattr(me, "id", "")),
                        "username": getattr(me, "username", "") or "",
                        "first_name": getattr(me, "first_name", "") or "",
                        "last_name": getattr(me, "last_name", "") or "",
                        "phone_number": phone,
                    },
                },
            }
        finally:
            await client.disconnect()

    if action == "logout":
        client = SoroushClient(StringSession(payload.get("string_session", "")))
        try:
            await client.connect()
            await client.log_out()
            return {"ok": True, "data": True}
        finally:
            await client.disconnect()

    if action == "get_user_channels":
        include_avatars = bool(payload.get("include_avatars", True))
        client = SoroushClient(StringSession(payload.get("string_session", "")))
        found: list[dict] = []
        media_senders: dict[tuple[str, int], Any] = {}
        try:
            await client.connect()
            if not await client.is_user_authorized():
                return {"ok": False, "error_kind": "permission", "error": "AUTH_KEY_UNREGISTERED"}

            dc_map = await _get_media_dc_map(client) if include_avatars else {}

            async for dlg in client.iter_dialogs(limit=150):
                if not getattr(dlg, "is_channel", False) or getattr(dlg, "is_group", False):
                    continue
                ent = dlg.entity
                is_creator = bool(getattr(ent, "creator", False))
                admin_rights = getattr(ent, "admin_rights", None)
                can_post = is_creator or bool(admin_rights and getattr(admin_rights, "post_messages", True))
                if not can_post:
                    continue

                avatar_b64 = ""
                if include_avatars:
                    try:
                        av = await _download_channel_avatar(client, ent, dc_map, media_senders)
                        if av:
                            avatar_b64 = base64.b64encode(av).decode("ascii")
                    except Exception:
                        avatar_b64 = ""

                uname = getattr(ent, "username", "") or ""
                access_hash = getattr(ent, "access_hash", None)
                found.append(
                    {
                        "chat_id": f"@{uname}" if uname else str(getattr(ent, "id", "")),
                        "numeric_id": str(getattr(ent, "id", "")),
                        "access_hash": str(access_hash) if access_hash is not None else "",
                        "title": (dlg.name or uname or f"کانال {getattr(ent, 'id', '')}")[:180],
                        "username": uname,
                        "avatar_b64": avatar_b64,
                    }
                )
            return {"ok": True, "data": found}
        finally:
            for sender in media_senders.values():
                try:
                    await sender.disconnect()
                except Exception:
                    pass
            await client.disconnect()

    if action == "send_text":
        client = SoroushClient(StringSession(payload.get("string_session", "")))
        try:
            await client.connect()
            entity = await _resolve_channel_entity(
                client,
                payload["chat_id"],
                access_hash=str(payload.get("access_hash") or ""),
            )
            msg = await client.send_message(entity, payload.get("text") or "")
            return {"ok": True, "data": {"message_id": str(getattr(msg, "id", ""))}}
        finally:
            await client.disconnect()

    return {"ok": False, "error": f"Unknown action: {action}"}


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        result = asyncio.run(_execute(payload))
    except Exception as exc:
        result = {
            "ok": False,
            "error": str(exc) or type(exc).__name__,
            "seconds": int(getattr(exc, "seconds", 0) or 0),
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
