from balethon.objects import ReplyKeyboard, ReplyKeyboardButton
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from django.conf import settings
from balethon import Client


class Command(BaseCommand):
    help = 'اجرای ربات بله برای اتصال حساب کاربری'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('ربات بله در حال اجرا است...'))

        bot = Client(settings.BALE_BOT_TOKEN)

        @sync_to_async
        def link_user_to_bale(phone_number, chat_id):
            if phone_number.startswith('+98'):
                phone_number = '0' + phone_number[3:]
            elif phone_number.startswith('98'):
                phone_number = '0' + phone_number[2:]

            from accounts.models import CustomUser
            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                user.bale_chat_id = str(chat_id)
                user.save()
                return user
            except CustomUser.DoesNotExist:
                return None

        @bot.on_message()
        async def handle_messages(message):
            chat_id = message.chat.id

            if message.text == "/start":
                keyboard = ReplyKeyboard(
                    [ReplyKeyboardButton("تایید شماره تماس 📱", request_contact=True)],
                    resize=True
                )

                await message.reply(
                    "سلام! \nبرای اتصال حساب کاربری سایت به این ربات و دریافت نوتیفیکیشن‌ها، روی دکمه زیر کلیک کنید:",
                    reply_markup=keyboard
                )

            elif message.contact:
                phone = message.contact.phone_number
                user = await link_user_to_bale(phone, chat_id)

                if user:
                    await message.reply(
                        f"عزیز دلم {user.nickname or 'کاربر گرامی'}، حساب شما با موفقیت به ربات متصل شد! 🎉\nاز این به بعد نوتیف‌ها رو اینجا دریافت می‌کنی.")
                else:
                    await message.reply(
                        "متاسفانه حسابی با این شماره تلفن در سایت پیدا نشد. اول در سایت ثبت‌نام کنید. ❌")

        bot.run()
