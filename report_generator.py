# report_generator.py
import os, datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from sqlalchemy import func
from database import db
from models import Category, Record, GeneratedReport, SmartReport  # ← لاحظ إضافة SmartReport

SOFT_RED_BG    = colors.HexColor("#FEE2E2")
SOFT_YELLOW_BG = colors.HexColor("#FEF9C3")
SOFT_GREEN_BG  = colors.HexColor("#DCFCE7")
RED_TXT    = colors.HexColor("#DC2626")
YELLOW_TXT = colors.HexColor("#CA8A04")
GREEN_TXT  = colors.HexColor("#16A34A")

BLUE_DARK  = colors.HexColor("#0055D4")
BLUE       = colors.HexColor("#007BFF")
GREY_LINE  = colors.HexColor("#E2E8F0")
GREY_HEAD  = colors.HexColor("#F8FAFC")

LEFT_MARGIN, RIGHT_MARGIN, TOP_MARGIN = 2*cm, 2*cm, 2.8*cm
PAGE_W, PAGE_H = A4
MAX_TABLE_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

def _nor_label(code):
    return {
        "reports":"Rapporter","deviations":"Avvik","workers":"Arbeidere",
        "environment":"Miljø","risk":"Risiko","ppe":"Verneutstyr",
        "emergency":"Beredskap","maintenance":"Vedlikehold"
    }.get(code, code.capitalize())

def _status_style(status: str):
    s = (status or "").strip().lower()
    if s in ("open","åpen"):                       return ("🔴 Åpen", SOFT_RED_BG, RED_TXT)
    if s in ("in_progress","processing","under behandling","under arbeid"):
                                                   return ("🟡 Under arbeid", SOFT_YELLOW_BG, YELLOW_TXT)
    if s in ("closed","lukket"):                   return ("🟢 Lukket", SOFT_GREEN_BG, GREEN_TXT)
    return (status or "-", colors.white, colors.black)

def _ensure_dir(p): os.makedirs(p, exist_ok=True)

def generate_category_report(category_code: str, upload_root: str, logo_path: str|None=None, created_by: str="Admin") -> str:
    cat = Category.query.filter_by(code=category_code).first()
    if not cat:
        raise ValueError("Category not found")

    # مسار الإخراج
    target_base = os.path.join(upload_root, category_code, "auto_reports")
    _ensure_dir(target_base)
    now = datetime.datetime.now()
    fname = f"HMS_Rapport_{_nor_label(category_code)}_{now.strftime('%Y-%m-%d_%H-%M')}_by_{created_by.replace(' ','_')}.pdf"
    out_path = os.path.join(target_base, fname)

    # === مصادر البيانات: قيود يدوية + تقارير ذكية
    latest_records = (db.session.query(Record)
                      .join(Category).filter(Category.code==category_code)
                      .order_by(Record.created_at.desc()).limit(10).all())

    latest_smart   = (SmartReport.query
                      .filter_by(category_code=category_code)
                      .order_by(SmartReport.created_at.desc()).limit(10).all())

    # أرقام عامة (يدوي)
    total_all = db.session.query(func.count(Record.id)).scalar() or 0
    total_cat = db.session.query(func.count(Record.id)).join(Category).filter(Category.code==category_code).scalar() or 0
    open_cat  = db.session.query(func.count(Record.id)).join(Category).filter(Category.code==category_code, Record.status=="open").scalar() or 0
    prog_cat  = db.session.query(func.count(Record.id)).join(Category).filter(Category.code==category_code, Record.status.in_(["in_progress","processing"])).scalar() or 0
    closed_cat= db.session.query(func.count(Record.id)).join(Category).filter(Category.code==category_code, Record.status=="closed").scalar() or 0

    # أرقام من التقارير الذكية
    total_smart = SmartReport.query.filter_by(category_code=category_code).count()
    smart_open  = SmartReport.query.filter_by(category_code=category_code, status="open").count()
    smart_proc  = SmartReport.query.filter(SmartReport.category_code==category_code, SmartReport.status.in_(["processing","in_progress"])).count()
    smart_closed= SmartReport.query.filter_by(category_code=category_code, status="closed").count()

    # PDF
    c = canvas.Canvas(out_path, pagesize=A4)
    if logo_path and os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, LEFT_MARGIN, PAGE_H - 2.6*cm, width=2.6*cm, height=2.6*cm, preserveAspectRatio=True, mask='auto')
        except:
            pass

    c.setFont("Helvetica-Bold", 14); c.setFillColor(BLUE_DARK)
    c.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 1.3*cm, "GE AMIGOS AS – HMS SYSTEM")
    c.setFont("Helvetica", 9); c.setFillColor(colors.black)
    c.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 1.9*cm, f"Generert: {now.strftime('%Y-%m-%d %H:%M')}  |  Av: {created_by}")

    c.setStrokeColor(BLUE); c.setLineWidth(2)
    c.line(LEFT_MARGIN, PAGE_H - TOP_MARGIN, PAGE_W - RIGHT_MARGIN, PAGE_H - TOP_MARGIN)
    c.setFont("Helvetica-Bold", 16); c.setFillColor(BLUE_DARK)
    c.drawString(LEFT_MARGIN, PAGE_H - TOP_MARGIN - 0.8*cm, f"HMS Rapport – {_nor_label(category_code)}")

    y = PAGE_H - TOP_MARGIN - 1.6*cm
    P = ParagraphStyle(name="P", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_LEFT, wordWrap="CJK")

    # 1) ملخص
    summary_data = [
        [Paragraph("<b>Nøkkeltall</b>", P), ""],
        ["Totalt (alle kategorier)", str(total_all)],
        [f"Totalt – {_nor_label(category_code)} (manuell)", str(total_cat)],
        [f"Åpen (manuell)", str(open_cat)],
        [f"Under arbeid (manuell)", str(prog_cat)],
        [f"Lukket (manuell)", str(closed_cat)],
        [f"Totalt – {_nor_label(category_code)} (smart)", str(total_smart)],
        [f"Åpen (smart)", str(smart_open)],
        [f"Under behandling (smart)", str(smart_proc)],
        [f"Lukket (smart)", str(smart_closed)],
    ]
    summary_table = Table(summary_data, colWidths=[8.2*cm, MAX_TABLE_W-8.2*cm])
    summary_table.setStyle(TableStyle([
        ("WORDWRAP",(0,0),(-1,-1),"CJK"),
        ("BACKGROUND",(0,0),(-1,0), GREY_HEAD),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("INNERGRID",(0,0),(-1,-1), 0.5, GREY_LINE),
        ("BOX",(0,0),(-1,-1), 0.75, GREY_LINE),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    _, sh = summary_table.wrap(MAX_TABLE_W, y-2*cm)
    summary_table.drawOn(c, LEFT_MARGIN, y - sh)
    y -= sh + 0.8*cm

    # 2) أحدث القيود اليدوية
    data_manual = [[Paragraph("<b>Siste 10 registreringer (manuell)</b>", P), "", "", ""],
                   ["Tittel", "Status", "Dato", "Opprettet av"]]
    if latest_records:
        for r in latest_records:
            label, bg, txt = _status_style(r.status)
            data_manual.append([
                Paragraph(r.title or "-", P),
                Paragraph(f'<font color="{txt}">{label}</font>', P),
                r.created_at.strftime("%Y-%m-%d %H:%M"),
                r.created_by or "-"
            ])
    else:
        data_manual.append(["Ingen data", "-", "-", "-"])
    col_widths = [7.6*cm, 3.0*cm, 3.1*cm, MAX_TABLE_W - (7.6*cm + 3.0*cm + 3.1*cm)]
    table_m = Table(data_manual, colWidths=col_widths, repeatRows=2, splitByRow=1)
    style_m = TableStyle([
        ("WORDWRAP",(0,0),(-1,-1),"CJK"),
        ("BACKGROUND",(0,0),(-1,0), GREY_HEAD),
        ("SPAN",(0,0),(-1,0)),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BACKGROUND",(0,1),(-1,1), colors.HexColor("#DBEAFE")),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),
        ("INNERGRID",(0,0),(-1,-1), 0.5, GREY_LINE),
        ("BOX",(0,0),(-1,-1), 0.75, GREY_LINE),
        ("ALIGN",(0,0),(-1,-1),"LEFT"),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ])
    for i, r in enumerate(latest_records, start=2):
        _, bg, _ = _status_style(r.status)
        style_m.add("BACKGROUND", (1,i), (1,i), bg)
    table_m.setStyle(style_m)
    _, th = table_m.wrap(MAX_TABLE_W, y-2*cm)
    table_m.drawOn(c, LEFT_MARGIN, y - th)
    y -= th + 0.8*cm

    # 3) أحدث التقارير الذكية
    data_smart = [[Paragraph("<b>Siste 10 smartrapporter</b>", P), "", ""],
                  ["Tittel", "Status", "Dato"]]
    if latest_smart:
        for s in latest_smart:
            label, bg, txt = _status_style(s.status)
            data_smart.append([
                Paragraph(s.title or "-", P),
                Paragraph(f'<font color="{txt}">{label}</font>', P),
                s.created_at.strftime("%Y-%m-%d %H:%M")
            ])
    else:
        data_smart.append(["Ingen data", "-", "-"])
    col2 = [10.0*cm, 3.0*cm, MAX_TABLE_W - (10.0*cm + 3.0*cm)]
    table_s = Table(data_smart, colWidths=col2, repeatRows=2, splitByRow=1)
    style_s = TableStyle([
        ("WORDWRAP",(0,0),(-1,-1),"CJK"),
        ("BACKGROUND",(0,0),(-1,0), GREY_HEAD),
        ("SPAN",(0,0),(-1,0)),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("BACKGROUND",(0,1),(-1,1), colors.HexColor("#DBEAFE")),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),
        ("INNERGRID",(0,0),(-1,-1), 0.5, GREY_LINE),
        ("BOX",(0,0),(-1,-1), 0.75, GREY_LINE),
        ("ALIGN",(0,0),(-1,-1),"LEFT"),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
    ])
    for i, s in enumerate(latest_smart, start=2):
        _, bg, _ = _status_style(s.status)
        style_s.add("BACKGROUND", (1,i), (1,i), bg)
    table_s.setStyle(style_s)
    _, th2 = table_s.wrap(MAX_TABLE_W, y-2*cm)
    table_s.drawOn(c, LEFT_MARGIN, y - th2)

    # (تشخيص) اطبع أعداد العناصر للمساعدة
    print(f"[GEN] cat={category_code} latest_manual={len(latest_records)} latest_smart={len(latest_smart)} totals(man={total_cat}, smart={total_smart})")

    c.showPage(); c.save()

    # سجل التقرير بقاعدة البيانات بحقول صحيحة
    rel_path = os.path.relpath(out_path, start=os.path.dirname(__file__))
    rec = GeneratedReport(category_code=category_code, file_path=rel_path, created_by=created_by)
    db.session.add(rec); db.session.commit()

    return out_path
