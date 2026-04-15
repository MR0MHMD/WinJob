from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    name = 'campaigns'
    verbose_name = 'کمپین'

    def ready(self):
        import campaigns.signals

