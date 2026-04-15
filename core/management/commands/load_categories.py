import os
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Category


class Command(BaseCommand):
    help = 'ایجاد دسته‌بندی‌های جامع شغلی به صورت سلسله‌مراتبی'

    CATEGORIES_DATA = {
        # 1. فناوری اطلاعات
        "فناوری-اطلاعات-ارتباطات": {
            "name": "فناوری اطلاعات و ارتباطات (IT & Digital)",
            "icon": "fa-laptop-code",
            "order": 1,
            "children": {
                "توسعه-نرم‌افزار": {
                    "name": "توسعه نرم‌افزار",
                    "children": {
                        "فرانت-اند": {"name": "برنامه‌نویس وب (فرانت‌اند)"},
                        "بک-اند": {"name": "برنامه‌نویس وب (بک‌اند)"},
                        "فول-استک": {"name": "برنامه‌نویس وب (فول‌استک)"},
                        "اندروید": {"name": "برنامه‌نویس موبایل (Android)"},
                        "آی-او-اس": {"name": "برنامه‌نویس موبایل (iOS)"},
                        "فلاتر": {"name": "برنامه‌نویس موبایل (Flutter)"},
                        "بازی": {"name": "توسعه‌دهنده بازی"},
                        "بلاکچین": {"name": "توسعه‌دهنده بلاکچین و کریپتو"}
                    }
                },
                "طراحی-گرافیک-دیجیتال": {
                    "name": "طراحی و گرافیک دیجیتال",
                    "children": {
                        "ui-ux": {"name": "طراح UI/UX"},
                        "گرافیک": {"name": "طراح گرافیک و موشن‌گرافیک"},
                        "انیمیشن": {"name": "انیماتور 2D/3D"},
                        "لوگو": {"name": "طراح لوگو و برندینگ"}
                    }
                },
                "امنیت-سایبری": {
                    "name": "امنیت سایبری و شبکه",
                    "children": {
                        "امنیت-شبکه": {"name": "متخصص امنیت شبکه"},
                        "هکر-اخلاقی": {"name": "هکر اخلاقی (Penetration Tester)"},
                        "مدیر-شبکه": {"name": "مدیر شبکه و سرور"},
                        "devops": {"name": "متخصص DevOps و Cloud"}
                    }
                },
                "هوش-مصنوعی": {
                    "name": "داده و هوش مصنوعی",
                    "children": {
                        "data-scientist": {"name": "دانشمند داده (Data Scientist)"},
                        "یادگیری-ماشین": {"name": "مهندس یادگیری ماشین"},
                        "data-analyst": {"name": "تحلیل‌گر داده (Data Analyst)"},
                        "big-data": {"name": "متخصص Big Data"}
                    }
                }
            }
        },

        # 2. بازاریابی
        "بازاریابی-تبلیغات-فروش": {
            "name": "بازاریابی، تبلیغات و فروش",
            "icon": "fa-bullhorn",
            "order": 2,
            "children": {
                "بازاریابی-دیجیتال": {
                    "name": "بازاریابی دیجیتال",
                    "children": {
                        "seo": {"name": "متخصص SEO و SEM"},
                        "شبکه-اجتماعی": {"name": "مدیر شبکه‌های اجتماعی (SMM)"},
                        "گوگل-ادز": {"name": "متخصص تبلیغات گوگل"},
                        "اینستاگرام": {"name": "متخصص تبلیغات اینستاگرام"},
                        "ایمیل": {"name": "ایمیل مارکتر و CRM"}
                    }
                },
                "فروش-تجارت": {
                    "name": "فروش و تجارت",
                    "children": {
                        "b2b": {"name": "مدیر فروش B2B"},
                        "b2c": {"name": "مدیر فروش B2C"},
                        "ecommerce": {"name": "فروشنده آنلاین (E-commerce)"},
                        "قرارداد": {"name": "مذاکره‌کننده قرارداد"},
                        "بازار": {"name": "تحلیل‌گر بازار"}
                    }
                }
            }
        },

        # 3. مدیریت
        "مدیریت-کسب‌وکار": {
            "name": "مدیریت و کسب‌وکار",
            "icon": "fa-briefcase",
            "order": 3,
            "children": {
                "مدیریت-اجرایی": {
                    "name": "مدیریت اجرایی",
                    "children": {"ceo": {"name": "مدیرعامل (CEO)"},
                        "مدیرکل": {"name": "مدیرکل"},
                        "pmp": {"name": "مدیر پروژه (PMP)"},
                        "hr": {"name": "مدیر منابع انسانی (HR)"},
                        "مالی": {"name": "مدیر مالی و حسابداری"}
                    }
                },
                "مشاوره": {
                    "name": "مشاوره و کسب‌وکار",
                    "children": {
                        "مشاور-مدیریت": {"name": "مشاور مدیریت"},
                        "مشاور-مالی": {"name": "مشاور مالی و سرمایه‌گذاری"},
                        "business-analyst": {"name": "تحلیل‌گر کسب‌وکار"},
                        "کوچ": {"name": "کوچینگ و توسعه فردی"}
                    }
                }
            }
        },

        # 4. تولید و مهندسی
        "تولید-صنعت-مهندسی": {
            "name": "تولید، صنعت و مهندسی",
            "icon": "fa-industry",
            "order": 4,
            "children": {
                "عمران-ساختمان": {
                    "name": "مهندسی عمران و ساختمانی",
                    "children": {
                        "عمران-محاسبات": {"name": "مهندس عمران (محاسبات)"},
                        "عمران-اجرا": {"name": "مهندس عمران (اجرا)"},
                        "معمار": {"name": "مهندس معمار"},
                        "تأسیسات-برق": {"name": "مهندس تأسیسات (برق)"},
                        "تأسیسات-مکانیک": {"name": "مهندس تأسیسات (مکانیک)"}
                    }
                },
                "مکانیک-برق": {
                    "name": "مهندسی مکانیک و برق",
                    "children": {
                        "مکانیک-طراحی": {"name": "مهندس مکانیک (طراحی)"},
                        "مکانیک-تولید": {"name": "مهندس مکانیک (تولید)"},
                        "برق-قدرت": {"name": "مهندس برق (قدرت)"},
                        "رباتیک": {"name": "مهندس رباتیک"},
                        "cnc": {"name": "تکنسین CNC"}
                    }
                }
            }
        },

        # 5. بهداشت
        "بهداشت-درمان": {
            "name": "بهداشت و درمان",
            "icon": "fa-user-md",
            "order": 5,
            "children": {
                "پزشکی-جراحی": {
                    "name": "پزشکی و جراحی",
                    "children": {
                        "پزشک-عمومی": {"name": "پزشک عمومی"},
                        "دندانپزشک": {"name": "دندانپزشک عمومی"},
                        "متخصص-داخلی": {"name": "پزشک متخصص (داخلی)"}
                    }
                },
                "پرستاری": {
                    "name": "پرستاری و پیراپزشکی",
                    "children": {
                        "پرستار-icu": {"name": "پرستار ICU"},
                        "ماما": {"name": "ماما"},
                        "فیزیوتراپی": {"name": "فیزیوتراپیست"}
                    }
                }
            }
        },

        # 6. آموزش
        "آموزش-تدریس": {
            "name": "آموزش و تدریس",
            "icon": "fa-graduation-cap",
            "order": 6,
            "children": {
                "آموزش-حضوری": {"name": "آموزش школьی و دانشگاهی"},
                "آموزش-آنلاین": {"name": "آموزش آنلاین و تخصصی"}
            }
        },

        # 7. خدمات
        "خدمات-گردشگری": {
            "name": "خدمات و گردشگری",
            "icon": "fa-utensils",
            "order": 7,
            "children": {
                "رستوران": {"name": "رستوران و پذیرایی"},
                "زیبایی": {"name": "خدمات زیبایی"}
            }
        }
    }

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 شروع ایجاد دسته‌بندی‌های شغلی...'))

        # پاک کردن داده‌های قبلی
        deleted_count, _ = Category.objects.all().delete()
        self.stdout.write(f'   🗑️  {deleted_count} دسته قبلی پاک شد')

        created_count = 0

        def create_category(slug, data, parent=None):
            nonlocal created_count

            category = Category.objects.create(
                name=data['name'],
                slug=slug,
                description=f"دسته‌بندی شغلی: {data['name']}",
                icon=data.get('icon', ''),
                parent=parent,
                order=data.get('order', 0),
                is_active=True
            )
            created_count += 1

            # ایجاد فرزندان
            if 'children' in data:
                child_order = 1
                for child_slug, child_data in data['children'].items():
                    create_category(child_slug, child_data, category)
                    child_order += 1

        # ایجاد ریشه‌ها
        for root_slug, root_data in self.CATEGORIES_DATA.items():
            create_category(root_slug, root_data)

        self.stdout.write(self.style.SUCCESS(f'✅ تمام! {created_count} دسته‌بندی ایجاد شد'))
        self.stdout.write(self.style.SUCCESS(f'📊 ریشه‌ها: {Category.objects.filter(parent__isnull=True).count()}'))
        self.stdout.write(self.style.SUCCESS('🌳 ساختار آماده استفاده است!'))