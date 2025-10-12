# smart_writer.py
import random
from datetime import datetime

def generate_smart_report(name, category, notes, date=None, location=None):
    """
    يولد نص تقرير كامل استناداً إلى مدخلات بسيطة.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    intro = f"تقرير ذكي متعلق بفئة ({category}) بتاريخ {date}."
    if name:
        intro += f" هذا التقرير باسم {name}."
    if location:
        intro += f" تمت ملاحظة الحالة في موقع {location}."

    # المعالجة الأساسية
    context = " ".join(notes.split("،")).strip()
    if len(context) < 10:
        context += " تم تسجيل ملاحظات مختصرة حول الحالة."

    # توليد تفاصيل منطقية بناءً على الكلمات المفتاحية
    lower = context.lower()
    if "زيت" in lower or "دهون" in lower:
        detail = "تمت ملاحظة تسرب زيت أو دهون في المنطقة المحددة مما تسبب بخطر انزلاق محتمل. تم تنظيف المنطقة فوراً واتخاذ الإجراءات الوقائية."
        actions = "تم استخدام مواد امتصاص خاصة وتنظيف المكان وإبلاغ مسؤول الصيانة للتأكد من مصدر التسرب."
        suggestion = "يوصى بتركيب حواجز أو إشعارات تحذيرية في مناطق تحوي مواد دهنية لتقليل خطر الانزلاق."
    elif "كهرب" in lower or "ماس" in lower:
        detail = "تم رصد خلل كهربائي أو ماس في أحد الأجهزة. تم عزل التيار مؤقتاً وتوثيق الحالة."
        actions = "جرى التواصل مع الفني المختص لفحص التمديدات الكهربائية والتأكد من عدم وجود مخاطر."
        suggestion = "يفضل تنفيذ فحص كهربائي شهري لجميع المعدات لتقليل احتمالية الأعطال."
    elif "نفايات" in lower or "فرز" in lower:
        detail = "لوحظت مشكلة في فرز النفايات أو التخلص منها بطريقة غير منظمة."
        actions = "تم التواصل مع الجهة المسؤولة عن جمع النفايات لإعادة تنظيم عملية الفرز وتوفير الحاويات المناسبة."
        suggestion = "يوصى بوضع لوحات إرشادية واضحة لتوضيح أنواع النفايات وأماكنها."
    else:
        detail = f"تم تسجيل ملاحظات حول الحالة التالية: {context}. بعد التقييم الميداني، تبين أن الحالة تتطلب مراقبة ومتابعة دورية."
        actions = "تم اتخاذ الإجراءات المناسبة وفقًا لسياسات المنشأة وتوثيق الحادث."
        suggestion = "يوصى بمراجعة الحالة خلال الأسبوع القادم لضمان استقرار الوضع."

    severity = random.choice(["منخفض", "متوسط", "مرتفع"])

    report = {
        "title": f"تقرير ذكي عن {category}",
        "intro": intro,
        "details": detail,
        "actions": actions,
        "suggestion": suggestion,
        "severity": severity,
        "created_at": date,
        "author": name or "غير محدد"
    }

    return report
