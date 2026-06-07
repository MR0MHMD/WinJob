import os
from celery import Celery

# تنظیم ماژول تنظیمات جنگو
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WinJob.settings')

app = Celery('WinJob')

# بارگذاری تنظیمات از فایل settings.py با پیشوند CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# کشف خودکار تسک‌ها از همه اپ‌های نصب شده
app.autodiscover_tasks()