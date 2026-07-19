import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WinJob.settings')

app = Celery('WinJob')

if getattr(settings, 'CELERY_ENABLED', False):
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()
else:
    app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
