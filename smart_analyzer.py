# smart_analyzer.py
def analyze(text: str):
    text_l = (text or "").lower()
    severity = "منخفض"
    tags = []
    suggestions = []

    high_kw = ["حريق", "دخان", "انفجار", "انزلاق", "كهرب", "ماس", "اختناق", "سم", "غاز"]
    med_kw  = ["تسريب", "زيوت", "دهون", "ملوث", "كسر", "تعطل", "انسكاب", "رطوبة"]

    score = 0
    for w in high_kw:
        if w in text_l:
            score += 2
            tags.append(w)
    for w in med_kw:
        if w in text_l:
            score += 1
            tags.append(w)

    if score >= 3:
        severity = "مرتفع"
    elif score == 2:
        severity = "متوسط"

    if any(k in text_l for k in ["دهون", "زيوت", "شحم"]):
        suggestions.append("جدولة تفريغ خزان الدهون ومراجعة سجل الصيانة.")
    if any(k in text_l for k in ["كهرب", "ماس", "قاطع"]):
        suggestions.append("استدعاء فني كهرباء وفحص القواطع وتوثيق القياسات.")
    if any(k in text_l for k in ["انزلاق", "انسكاب", "رطوبة"]):
        suggestions.append("تجفيف الأرضية ووضع لافتات تحذيرية وفحص التسريب.")
    if any(k in text_l for k in ["نفايات", "فرز", "بلدية"]):
        suggestions.append("مراسلة البلدية رسميًا وتوثيق الرد وخطة مؤقتة للفرز.")

    tags = list(dict.fromkeys(tags))
    suggestions = list(dict.fromkeys(suggestions))

    return {
        "severity": severity,
        "tags": tags,
        "suggestions": suggestions
    }
