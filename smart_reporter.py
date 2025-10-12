# smart_reporter.py
# -*- coding: utf-8 -*-
"""
توليد PDF منسّق للتقارير الذكية:
- عنوان
- شارة حالة ملونة (Åpen / Under behandling / Løst)
- ميتاداتا (Kategori, Dato, Opprettet av, Språk)
- نص التقرير المنسق
- جدول تقييم المخاطر
"""

import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def build_paths(uploads_root: str, category_code: str, report_id: int):
    """
    يُعيد مسار المجلد واسم الملف النهائي:
      uploads/<category>/smart_reports/smart_<category>_<id>.pdf
    """
    base_dir = os.path.join(uploads_root, category_code, "smart_reports")
    ensure_dir(base_dir)
    pdf_name = f"smart_{category_code}_{report_id}.pdf"
    return base_dir, pdf_name, None  # html_name محجوز لاحقًا

def _new_page_if_needed(c: canvas.Canvas, y: float, min_y: float = 2.5*cm) -> float:
    if y < min_y:
        c.showPage()
        return A4[1] - 2.5*cm
    return y

def draw_wrapped(c: canvas.Canvas, x: float, y: float, text: str,
                 width_chars: int = 95, leading: int = 14,
                 font: str = "Helvetica", size: int = 10) -> float:
    """
    لفّ نص بسيط على عدد أحرف تقريبي لكل سطر (سهل وسريع).
    يضيف صفحات جديدة عند الحاجة.
    """
    c.setFont(font, size)
    for para in (text or "").splitlines():
        buf = ""
        words = para.split()
        if not words:
            y -= leading // 2
            y = _new_page_if_needed(c, y)
            continue
        for w in words:
            if len((buf + " " + w).strip()) <= width_chars:
                buf = (buf + " " + w).strip()
            else:
                c.drawString(x, y, buf)
                y -= leading
                y = _new_page_if_needed(c, y)
                buf = w
        if buf:
            c.drawString(x, y, buf)
            y -= leading
            y = _new_page_if_needed(c, y)
        y -= 4
        y = _new_page_if_needed(c, y)
    return y

def draw_table(c: canvas.Canvas, x: float, y: float, data,
               col_widths=(3*cm, 9*cm, 5*cm), row_h: int = 16) -> float:
    """
    جدول بسيط لثلاثة أعمدة (Risiko, Beskrivelse, Tiltak).
    يضيف صفحات جديدة عند الحاجة.
    """
    if not data:
        return y
    table_w = sum(col_widths)
    for r, row in enumerate(data):
        y = _new_page_if_needed(c, y, min_y=3*cm)
        bg = colors.lightgrey if r == 0 else colors.whitesmoke
        c.setFillColor(bg)
        c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=0)
        c.setFillColor(colors.black)

        cx = x
        for i, cell in enumerate(row[:3]):  # نضمن ثلاثة أعمدة
            c.rect(cx, y - row_h, col_widths[i], row_h, fill=0, stroke=1)
            txt = str(cell) if cell is not None else ""
            c.setFont("Helvetica", 9)
            c.drawString(cx + 4, y - row_h + 4, txt[:120])  # قصّة خفيفة داخل الخلية
            cx += col_widths[i]
        y -= row_h
    return y - 6

def render_pdf(pdf_path: str, meta: dict, logo_path: str | None = None) -> None:
    """
    main renderer
    meta المتوقعة:
      title, status(open/processing/closed), category_code, date, created_by,
      lang, severity, description, table_rows
    """
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4
    x = 2*cm
    y = h - 2.2*cm

    # شعار (اختياري)
    if logo_path and os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, w - 4*cm, h - 3*cm, width=2.5*cm, height=2.5*cm, mask='auto')
        except Exception:
            pass

    # عنوان
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, meta.get("title", "HMS Smartrapport"))
    y -= 18

    # شارة الحالة الملونة
    status = (meta.get("status") or "open").strip().lower()
    if status == "closed":
        color = (0, 0.6, 0); label = "Løst"
    elif status == "processing":
        color = (1, 0.8, 0); label = "Under behandling"
    else:
        color = (1, 0, 0); label = "Åpen sak"
    c.setFillColorRGB(*color)
    c.roundRect(x, y - 12, 145, 16, 3, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 6, y - 9, label)
    c.setFillColor(colors.black)
    y -= 26

    # ميتاداتا
    c.setFont("Helvetica", 10)
    meta_lines = [
        f"Kategori: {meta.get('category_code','')}",
        f"Dato: {meta.get('date','')}",
        f"Opprettet av: {meta.get('created_by','')}",
        f"Språk: {meta.get('lang','no').upper()}",
    ]
    for line in meta_lines:
        c.drawString(x, y, line)
        y -= 14
        y = _new_page_if_needed(c, y)

    y -= 6
    y = _new_page_if_needed(c, y)

    # نص التقرير
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Rapporttekst:")
    y -= 14
    y = draw_wrapped(c, x, y, meta.get("description", ""), 95, leading=14)

    # جدول تقييم المخاطر
    rows = meta.get("table_rows") or []
    if rows:
        c.setFont("Helvetica-Bold", 12)
        y = _new_page_if_needed(c, y)
        c.drawString(x, y, "Risikovurdering:")
        y -= 16
        y = draw_table(c, x, y, rows)

    # إنهاء
    c.showPage()
    c.save()
