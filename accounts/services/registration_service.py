from django.db import transaction
from accounts.models import CustomUser
from advertisers.models import AdvertiserProfile
from influencers.models import InfluencerProfile
from content_team.models import ContentTeamMember


class RegistrationService:

    @staticmethod
    @transaction.atomic
    def register_advertiser(phone_number, password=None, nickname=None, **profile_data):
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise ValueError("این شماره تلفن قبلاً ثبت شده است")

        user = CustomUser.objects.create_user(
            phone_number=phone_number,
            password=password,
            nickname=nickname
        )

        advertiser = AdvertiserProfile.objects.create(
            user=user,
            business_name=nickname or f"user-{phone_number}",
            **profile_data
        )

        return user, advertiser

    @staticmethod
    @transaction.atomic
    def register_influencer(phone_number, password=None, nickname=None, **profile_data):
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise ValueError("این شماره تلفن قبلاً ثبت شده است")

        user = CustomUser.objects.create_user(
            phone_number=phone_number,
            password=password,
            nickname=nickname
        )

        influencer = InfluencerProfile.objects.create(
            user=user,
            full_name=nickname or f"user-{phone_number}",
            **profile_data
        )

        return user, influencer

    @staticmethod
    @transaction.atomic
    def register_team_member(phone_number, password, nickname, team, is_manager=False):
        """
        ثبت نام کاربر به عنوان عضو تیم

        Args:
            phone_number: شماره تلفن
            password: رمز عبور
            nickname: نام مستعار
            team: تیم مورد نظر
            is_manager: آیا کاربر مدیر تیم است؟ (در ساخت تیم جدید True است)
        """
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise ValueError("این شماره تلفن قبلاً ثبت شده است")

        user = CustomUser.objects.create_user(
            phone_number=phone_number,
            password=password,
            nickname=nickname
        )

        if is_manager:
            team_role = ContentTeamMember.Role.MANAGER
        else:
            team_role = ContentTeamMember.Role.OTHER

        team_member = ContentTeamMember.objects.create(
            user=user,
            team=team,
            role=team_role,
            is_active=True
        )

        return user, team_member
