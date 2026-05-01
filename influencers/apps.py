from django.apps import AppConfig


class InfluencersConfig(AppConfig):
    name = 'influencers'
    verbose_name = 'ناشر'

    def ready(self):
        import influencers.signals
