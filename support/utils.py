from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db.models import Q


def is_support_user(user):
    return user.is_authenticated and (user.has_platform_scope or user.is_staff
                                      or user.groups.filter(name='Support').exists())


def scope_support_queryset(user, queryset):
    """Scope management data; unknown/unlinked resources fail closed for platform managers."""
    if not getattr(user, 'has_platform_scope', False):
        return queryset
    label = queryset.model._meta.label_lower
    paths = {
        'core.platform': ('slug',),
        'campaigns.campaign': ('platform__slug',),
        'influencers.channel': ('platform__slug',),
        'influencers.channelbooking': ('campaign__platform__slug', 'channel__platform__slug'),
        'campaigns.campaignreport': (
            'campaign_influencer__campaign__platform__slug',
            'campaign_influencer__channel__platform__slug',
        ),
        'tickets.ticket': ('campaign__platform__slug',),
        'content_team.contentorder': ('campaign__platform__slug',),
        'content_team.contentdelivery': ('order__campaign__platform__slug',),
        'content_team.contentorderrevision': ('order__campaign__platform__slug',),
    }
    if label in paths:
        for path in paths[label]:
            # Missing platform is never considered a non-Instagram platform.
            queryset = queryset.filter(**{path + '__isnull': False})
            if user.is_human_media_manager:
                queryset = queryset.filter(**{path + '__iexact': 'instagram'})
            else:
                queryset = queryset.exclude(**{path + '__iexact': 'instagram'})
        return queryset

    def scoped(model):
        return scope_support_queryset(user, apps.get_model(model).objects.all())

    if label == 'accounts.customuser':
        return queryset.filter(
            Q(pk__in=scoped('campaigns.Campaign').values('advertiser__user_id')) |
            Q(pk__in=scoped('influencers.Channel').values('influencer__user_id'))
        )
    if label == 'advertisers.advertiserprofile':
        return queryset.filter(pk__in=scoped('campaigns.Campaign').values('advertiser_id'))
    if label == 'influencers.influencerprofile':
        return queryset.filter(pk__in=scoped('influencers.Channel').values('influencer_id'))
    if label == 'payment.transaction':
        return queryset.filter(
            Q(campaign_id__in=scoped('campaigns.Campaign').values('pk')) |
            Q(campaign__isnull=True, invoice__campaign_id__in=scoped('campaigns.Campaign').values('pk'))
        )
    if label == 'notifications.notification':
        allowed = Q(pk__in=[])
        for names, model in (
            (('Campaign',), 'campaigns.Campaign'),
            (('ChannelBooking', 'campaign_influencer'), 'influencers.ChannelBooking'),
            (('Ticket',), 'tickets.Ticket'),
            (('ContentOrder',), 'content_team.ContentOrder'),
            (('ContentDelivery',), 'content_team.ContentDelivery'),
            (('ContentOrderRevision',), 'content_team.ContentOrderRevision'),
        ):
            for name in names:
                allowed |= Q(related_content_type__iexact=name,
                             related_object_id__in=scoped(model).values('pk'))
        return queryset.filter(allowed)
    return queryset.none()


class PlatformManagerAdminGuard:
    """Scoped managers use the scoped support panel, never the unrestricted admin."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if (getattr(request.user, 'has_platform_scope', False)
                and request.resolver_match
                and 'admin' in request.resolver_match.namespaces):
            raise PermissionDenied('برای این نقش از پنل پشتیبانی استفاده کنید.')
