# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.db import transaction
# from influencers.models import CampaignReport
# from campaigns.models import Campaign, CampaignInfluencer
# from content_team.models import ContentOrder, ContentOrderRevision, ContentDelivery
# from accounts.models import Transaction
#
# from .utils import (
#     notify_advertiser_campaign_pending,
#     notify_advertiser_campaign_approved,
#     notify_advertiser_campaign_rejected,
#     notify_advertiser_influencer_accepted,
#     notify_advertiser_report_approved,
#     notify_advertiser_ticket_answered,
#     notify_advertiser_campaign_completed,
#     notify_influencer_new_order,
#     notify_influencer_penalty,
#     notify_influencer_report_approved,
#     notify_influencer_wallet_deposit,
#     notify_influencer_withdrawal_success,
#     notify_content_team_new_order,
#     notify_content_team_revision_requested,
#     notify_content_team_final_accepted,
#     notify_content_team_wallet_deposit,
#     notify_content_team_withdrawal_success,
# )
#
#
# # ==================== کمپین (تبلیغ‌دهنده) ====================
#
# @receiver(post_save, sender=Campaign)
# def campaign_status_notification(sender, instance, created, **kwargs):
#     if created:
#         # کمپین جدید ساخته شد - در انتظار تایید
#         notify_advertiser_campaign_pending(instance)
#     else:
#         # بررسی تغییر وضعیت
#         old = sender.objects.get(pk=instance.pk)
#         if old.status != instance.status:
#             if instance.status == 'approved':
#                 notify_advertiser_campaign_approved(instance)
#             elif instance.status == 'rejected':
#                 notify_advertiser_campaign_rejected(instance)
#             elif instance.status == 'completed':
#                 notify_advertiser_campaign_completed(instance)
#
#
# # ==================== اینفلوئنسر سفارش ====================
#
# @receiver(post_save, sender=CampaignInfluencer)
# def campaign_influencer_notification(sender, instance, created, **kwargs):
#     if created:
#         # سفارش جدید برای اینفلوئنسر
#         notify_influencer_new_order(instance)
#     else:
#         old = sender.objects.get(pk=instance.pk)
#
#         # اینفلوئنسر سفارش رو قبول کرد
#         if old.status != instance.status and instance.status == 'accepted':
#             notify_advertiser_influencer_accepted(instance)
#
#         # جریمه (اگر فیلد penalty دارید)
#         if hasattr(instance, 'penalty_amount') and instance.penalty_amount > 0:
#             if old.penalty_amount != instance.penalty_amount:
#                 notify_influencer_penalty(instance, instance.penalty_amount, instance.penalty_reason)
#
#
# @receiver(post_save, sender=CampaignReport)
# def campaign_report_notification(sender, instance, created, **kwargs):
#     if not created and instance.status == 'approved':
#         # گزارش توسط ادمین تایید شد
#         notify_advertiser_report_approved(instance.campaign_influencer)
#         notify_influencer_report_approved(instance.campaign_influencer)
#
#
# # ==================== تراکنش‌ها (کیف پول) ====================
#
# @receiver(post_save, sender=Transaction)
# def transaction_notification(sender, instance, created, **kwargs):
#     if created and instance.status == 'success':
#         if instance.type in ['influencer_payment', 'deposit']:
#             # بررسی کن کاربر اینفلوئنسر هست یا تبلیغ‌دهنده
#             if hasattr(instance.user, 'influencer_profile'):
#                 notify_influencer_wallet_deposit(instance)
#
#         elif instance.type == 'team_payment':
#             if instance.team_member:
#                 team = instance.team_member.team
#                 notify_content_team_wallet_deposit(instance, team)
#
#
# # ==================== تیم محتوا ====================
#
# @receiver(post_save, sender=ContentOrder)
# def content_order_notification(sender, instance, created, **kwargs):
#     if created:
#         notify_content_team_new_order(instance)
#
#
# @receiver(post_save, sender=ContentOrderRevision)
# def content_revision_notification(sender, instance, created, **kwargs):
#     if created:
#         notify_content_team_revision_requested(instance.order)
#
#
# @receiver(post_save, sender=ContentDelivery)
# def content_delivery_notification(sender, instance, created, **kwargs):
#     if not created:
#         old = sender.objects.get(pk=instance.pk)
#         if old.status != instance.status and instance.status == 'final_accepted':
#             notify_content_team_final_accepted(instance.order)