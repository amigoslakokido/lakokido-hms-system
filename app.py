# app.py
# -*- coding: utf-8 -*-
from flask import Flask, render_template, render_template_string, request, redirect, url_for, jsonify, session, send_from_directory, abort
import os, json, datetime
from werkzeug.utils import secure_filename
from config import Config
from database import db
from sqlalchemy import text, func

from models import (
    User, Category, Record, RecordAttachment,
    ConfigSetting, GeneratedReport, SmartReport, seed_categories_if_needed
)

from report_generator import generate_category_report
from apscheduler.schedulers.background import BackgroundScheduler

# === Smart / AI ===
# لو ملف smart_ai.py غير موجود، خلي الاستيراد كما هو وسيشتغل الفرع الاحتياطي
try:
    from smart_ai import generate_deep_hms_report
except Exception:
    generate_deep_hms_report = None

from smart_reporter import render_pdf, build_paths

# ------------------ إعدادات عامة ------------------
ALLOWED_EXTS = {"jpg", "jpeg", "png", "pdf"}

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# ===== مسارات وتهيئة أساسية بعد إنشاء app =====
BASE_DIR   = os.path.dirname(__file__)
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

UPLOAD_DIRS = {
    "reports":     os.path.join(UPLOAD_ROOT, "reports"),
    "deviations":  os.path.join(UPLOAD_ROOT, "deviations"),
    "workers":     os.path.join(UPLOAD_ROOT, "workers"),
    "environment": os.path.join(UPLOAD_ROOT, "environment"),
    "risk":        os.path.join(UPLOAD_ROOT, "risk"),
    "ppe":         os.path.join(UPLOAD_ROOT, "ppe"),
    "emergency":   os.path.join(UPLOAD_ROOT, "emergency"),
    "maintenance": os.path.join(UPLOAD_ROOT, "maintenance"),
}

NOR_LABELS = {
    "reports":"Rapporter","deviations":"Avvik","workers":"Arbeidere",
    "environment":"Miljø","risk":"Risikovurdering","ppe":"Verneutstyr",
    "emergency":"Beredskap","maintenance":"Vedlikehold"
}

def ensure_upload_dirs():
    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    for p in UPLOAD_DIRS.values():
        os.makedirs(p, exist_ok=True)
        os.makedirs(os.path.join(p, "auto_reports"), exist_ok=True)
        os.makedirs(os.path.join(p, "smart_reports"), exist_ok=True)
        os.makedirs(os.path.join(p, "manual_reports"), exist_ok=True)

# --- إصلاح مخطط قاعدة البيانات للحالات القديمة (إضافة أعمدة إن لزم) ---
def _ensure_column(table: str, col: str, col_def: str):
    try:
        info = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
        cols = {row[1] for row in info}
        if col not in cols:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_def}"))
            db.session.commit()
            print(f"[Schema] Added column '{col}' to '{table}'.")
    except Exception as e:
        print(f"[Schema] Error while ensuring column {table}.{col}: {e}")

def ensure_smart_reports_schema():
    _ensure_column("smart_reports", "status",   "status VARCHAR(20) DEFAULT 'open'")
    _ensure_column("smart_reports", "pdf_path", "pdf_path TEXT")
    _ensure_column("smart_reports", "html_path","html_path TEXT")

# ---------- HEALTH & DEBUG ----------
@app.route("/_health")
def _health():
    return "OK", 200

@app.route("/api/categories")
def api_categories():
    items = [{"code": c, "label": NOR_LABELS.get(c, c.capitalize())} for c in UPLOAD_DIRS.keys()]
    return jsonify({"ok": True, "items": items})

@app.route("/_test/pdf")
def _test_pdf():
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    out_dir = os.path.join(UPLOAD_ROOT, "test")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "hello.pdf")
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(72, 800, "HELLO PDF — ReportLab works ✅")
    c.showPage(); c.save()
    rel = os.path.relpath(out_path, start=os.path.dirname(__file__))
    return jsonify({"ok": True, "file": rel})

@app.route("/_debug/seed", methods=["POST","GET"])
def _debug_seed():
    import json as _json
    category = (request.args.get("category") or request.form.get("category") or "deviations").strip()
    cat = Category.query.filter_by(code=category).first()
    if not cat:
        return jsonify({"ok": False, "error": "no_category"}), 400

    db.session.add(Record(category_id=cat.id, title="Eksponert ledning ved kassa", description="Synlig kobber, risiko støt/brann.", status="open", created_by="seed"))
    db.session.add(Record(category_id=cat.id, title="Vann på gulv ved oppvask", description="Fare for glidning.", status="in_progress", created_by="seed"))
    db.session.add(Record(category_id=cat.id, title="Filter ventilasjon renset", description="Utført vedlikehold.", status="closed", created_by="seed"))

    db.session.add(SmartReport(category_code=category, title="Elektrisk fare – eksponert kabel",
                               description="Automatisk demo-tekst om risiko og tiltak.", severity="Høy",
                               created_by="seed", status="open", lang="no",
                               tags_json=_json.dumps([]), suggestions_json=_json.dumps([])))
    db.session.add(SmartReport(category_code=category, title="Renhold – vått gulv lukket",
                               description="Tiltak gjennomført, verifisert.", severity="Middels",
                               created_by="seed", status="closed", lang="no",
                               tags_json=_json.dumps([]), suggestions_json=_json.dumps([])))
    db.session.commit()
    return jsonify({"ok": True, "seeded_category": category})

# ------------------ اللغات ------------------
def load_lang(code: str):
    lang_dir = app.config.get("LANG_DIR") or os.path.join(BASE_DIR, "langs")
    os.makedirs(lang_dir, exist_ok=True)
    p = os.path.join(lang_dir, f"{code}.json")
    if not os.path.exists(p):
        p = os.path.join(lang_dir, "no.json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

@app.before_request
def ensure_lang():
    if "lang" not in session:
        session["lang"] = "no"  # افتراضي نرويجي

@app.route("/set_lang/<code>")
def set_lang(code):
    if code in ["ar", "en", "no"]:
        session["lang"] = code
    return redirect(request.referrer or url_for("dashboard"))

# ------------------ الرئيسية ------------------
@app.route("/")
def dashboard():
    t = load_lang(session.get("lang", "no"))
    return render_template("smart_dashboard.html", t=t)

# ------------------ أجزاء الفئات (partials) ------------------
FORM_FILES = {
    "reports":"reports.html",
    "deviations":"deviations.html",
    "workers":"workers.html",
    "environment":"environment.html",
    "risk":"risk.html",
    "ppe":"ppe.html",
    "emergency":"emergency.html",
    "maintenance":"maintenance.html",
}

@app.route("/forms/<category>")
def get_form_partial(category):
    if category not in FORM_FILES:
        abort(404)
    return render_template(f"forms/{FORM_FILES[category]}")

# ------------------ CRUD مختصر للسجلات ------------------
@app.route("/api/records")
def api_records():
    code = request.args.get("category", "")
    q = Record.query.join(Category)
    if code:
        q = q.filter(Category.code == code)
    rows = q.order_by(Record.created_at.desc()).limit(500).all()
    return jsonify({"records": [r.to_dict() for r in rows]})

# ------------------ تنزيل المرفقات/التقارير ------------------
@app.route("/uploads/<category>/<path:filename>")
def download_attachment(category, filename):
    if category not in UPLOAD_DIRS:
        abort(404)
    base_dir = UPLOAD_DIRS[category]
    full_path = os.path.join(base_dir, filename)
    if os.path.exists(full_path):
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True)
    # جرّب داخل auto_reports
    alt_path = os.path.join(base_dir, "auto_reports", os.path.basename(filename))
    if os.path.exists(alt_path):
        return send_from_directory(os.path.dirname(alt_path), os.path.basename(alt_path), as_attachment=True)
    abort(404)

# ====== صفحة مجلد التقارير (Åpne mappe) ======
@app.route("/reports/<category>")
def list_category_reports(category):
    if category not in UPLOAD_DIRS:
        abort(404)
    auto_dir = os.path.join(UPLOAD_DIRS[category], "auto_reports")
    os.makedirs(auto_dir, exist_ok=True)

    files = []
    for name in sorted(os.listdir(auto_dir)):
        if name.lower().endswith(".pdf"):
            url = url_for("download_attachment", category=category, filename=os.path.join("auto_reports", name))
            files.append((name, url))

    items = "\n".join([f'<li><a href="{u}" target="_blank">{n}</a></li>' for n, u in files]) or "<li>Ingen rapporter ennå.</li>"
    title = f"Rapporter – {NOR_LABELS.get(category, category.capitalize())}"
    html = f"""<!doctype html><html lang="no"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:Helvetica,Arial,sans-serif;padding:20px}} h1{{font-size:18px;margin-bottom:10px}}
ul{{line-height:1.9}} a{{text-decoration:none}} a:hover{{text-decoration:underline}}</style></head>
<body><h1>{title}</h1><ul>{items}</ul></body></html>"""
    return html

# ============================================================
#                         SMART REPORTS
# تدفّق: إدخال ➜ معاينة فورية بدون حفظ ➜ اختيار الحالة ➜ حفظ + PDF ➜ عرض/تنزيل
# ============================================================

# 1) نموذج الإدخال
@app.route("/smart_report/new")
def smart_report_new():
    category = (request.args.get("category") or "").strip()
    if category not in UPLOAD_DIRS:
        abort(404)
    return render_template("smart_report_form.html", category=category)

# 2) معاينة فورية (ذكاء + حقن كهرباء عند الكلمات المفتاحية)
@app.route("/smart_report/preview", methods=["POST"])
def smart_report_preview():
    import re
    g = request.form.get

    category   = (g("category") or "").strip()
    reporter   = (g("reporter") or "admin").strip()
    date_str   = (g("date") or datetime.datetime.now().strftime("%Y-%m-%d")).strip()

    location   = (g("location") or g("site") or g("الموقع") or "").strip()
    incident   = (g("incident_type") or g("نوع_الحادث") or "").strip()
    root_cause = (g("root_cause") or g("السبب_الجذري") or "").strip()
    impact     = (g("impact") or g("result") or g("النتيجة") or "").strip()

    act_i = (g("immediate_actions")  or g("actions_immediate")  or g("إجراءات_عاجلة")    or "").strip()
    act_c = (g("corrective_actions") or g("actions_corrective") or g("إجراءات_تصحيحية")  or "").strip()
    act_p = (g("preventive_actions") or g("actions_preventive") or g("إجراءات_وقائية")    or "").strip()

    responsible = (g("responsible") or g("المسؤول") or reporter).strip()
    due_date    = (g("due_date") or g("deadline") or g("الموعد") or "").strip()
    risk_before = (g("risk_before") or g("likelihood") or g("مستوى_الخطر") or "Middels").strip()
    free_notes  = (g("details") or g("ملاحظات") or "").strip()

    if category not in UPLOAD_DIRS:
        abort(400)

    # ملاحظات موحّدة لإطعام الذكاء
    notes_lines = [
        f"Sted: {location}" if location else "",
        f"Hendelsestype: {incident}" if incident else "",
        f"Rotårsak: {root_cause}" if root_cause else "",
        f"Konsekvens/effekt: {impact}" if impact else "",
        f"Akutte tiltak (innmeldt): {act_i}" if act_i else "",
        f"Korrigerende tiltak (innmeldt): {act_c}" if act_c else "",
        f"Forebyggende tiltak (innmeldt): {act_p}" if act_p else "",
        f"Ansvarlig: {responsible}" if responsible else "",
        f"Frist: {due_date}" if due_date else "",
        f"Fritekst: {free_notes}" if free_notes else "",
        f"Forhåndsvurdert risiko: {risk_before}",
    ]
    notes = "\n".join([x for x in notes_lines if x])

    # توليد عميق إن توفّر smart_ai، وإلا نولّد من المدخلات
    sections, actions, risk_table = [], [], []
    title, severity, status = f"Hendelsesrapport – {NOR_LABELS.get(category, category.capitalize())}", "Middels", "open"

    try:
        if generate_deep_hms_report:
            gen = generate_deep_hms_report(notes=notes, category=category, reporter=reporter, status="open")
            sections   = gen.get("sections", [])
            actions    = gen.get("actions", [])
            risk_table = gen.get("risk_table", [])
            title      = gen.get("title", title)
            severity   = gen.get("severity", severity)
            status     = gen.get("status", status)
        else:
            raise RuntimeError("smart_ai not available")
    except Exception:
        # احتياطي
        sections = [
            {"title":"Sammendrag", "body": f"Hendelse registrert på {location or 'ukjent sted'}. Foreløpig risiko: {severity}."},
            {"title":"Tema", "body": incident or "Ikke spesifisert"},
            {"title":"Observasjoner", "body": impact or "—"},
            {"title":"Årsaksanalyse (5 hvorfor)", "body": root_cause or "—"},
            {"title":"Risikovurdering", "body": f"Forhåndsvurdert nivå før tiltak: {severity}."},
            {"title":"Tiltaksplan", "body": "Se tabellen nedenfor."},
            {"title":"Etterlevelse", "body": "Vurdert mot HMS/HACCP for restaurantdrift."},
            {"title":"Konklusjon", "body": "Tiltak følges opp til lukking."},
        ]
        if act_i: actions.append({"tiltak": act_i, "ansvar": responsible, "frist": due_date or "+1 dag", "status":"Planlagt"})
        if act_c: actions.append({"tiltak": act_c, "ansvar": responsible, "frist": due_date or "+7 dager", "status":"Planlagt"})
        if act_p: actions.append({"tiltak": act_p, "ansvar": "HMS-ansvarlig", "frist": "+14 dager", "status":"Planlagt"})
        risk_table = [["Risiko","Beskrivelse","Tiltak"],
                      [severity, (impact or "Foreløpig vurdering"), (act_i or act_c or act_p or "Oppfølging")]]

    # حقن ذكي لخطر الكهرباء حسب الكلمات
    text_all = " ".join([notes, free_notes, incident]).lower()
    if re.search(r"(سلك|كهرب|electri|strøm|ledning)", text_all):
        severity = "Høy"
        title = "Hendelsesrapport – Elektrisk fare (eksponert ledning)"
        sections = [
            {"title":"Sammendrag", "body": f"Oppdaget eksponert elektrisk ledning i {location or 'ukjent område'}. Umiddelbar avsperring og varsling. Risiko vurdert som Høy."},
            {"title":"Tema", "body": "Elektrisk fare – eksponert ledning"},
            {"title":"Bakgrunn", "body": (free_notes or "—")},
            {"title":"Observasjoner", "body": (impact or "Fare for elektrisk støt, brann og personskade ved berøring.")},
            {"title":"Årsaksanalyse (5 hvorfor)", "body": (root_cause or "Foreløpig antatt: mekanisk skade/feil montasje/manglende vedlikehold.")},
            {"title":"Risikovurdering", "body": "Sannsynlighet: Middels–Høy. Konsekvens: Alvorlig. Samlet nivå: Høy før tiltak."},
            {"title":"Tiltaksplan", "body": "Se tabellen for akutte, korrigerende og forebyggende tiltak."},
            {"title":"Etterlevelse", "body": "Krav iht. NEK 400, internkontrollforskriften og bedriftens HMS-rutiner."},
            {"title":"Konklusjon", "body": "Tiltak gjennomføres umiddelbart. Saken lukkes etter verifikasjon fra autorisert elektriker."},
        ]
        actions = [
            {"tiltak":"Sperr området og kutt strømkrets hvis mulig.", "ansvar":"Skiftleder", "frist":"Straks", "status":"Igangsatt"},
            {"tiltak":"Isoler مؤقتًا الموصل المكشوف حتى يصل الكهربائي.", "ansvar":"HMS-ansvarlig", "frist":"Straks", "status":"Planlagt"},
            {"tiltak":"Kontakt autorisert elektriker لاصلاح دائم وتوثيق.", "ansvar":"Daglig leder", "frist":"+1 dag", "status":"Planlagt"},
            {"tiltak":"Kontroller kabler مجاورة وتحديث logg vedlikehold.", "ansvar":"HMS-ansvarlig", "frist":"+3 dager", "status":"Planlagt"},
            {"tiltak":"Vernerunde سريعة وتذكير بإبلاغ avvik.", "ansvar":"Verneombud", "frist":"+7 dager", "status":"Planlagt"},
        ]
        risk_table = [
            ["Risiko","Beskrivelse","Tiltak (før/etter)"],
            ["Høy","Eksponert elektrisk ledning; støt/brannskade","FØR: Avsperring/strøm av. ETTER: Fagmessig utbedring + kontroll."],
        ]
        status = "open"

    description = "\n\n".join([f"{s['title']}:\n{s['body']}" for s in sections])

    return render_template(
        "smart_report_preview.html",
        category=category, reporter=reporter, date=date_str,
        title=title, description=description, severity=severity, status=status,
        sections=json.dumps(sections, ensure_ascii=False),
        actions=json.dumps(actions, ensure_ascii=False),
        risk_table=json.dumps(risk_table, ensure_ascii=False),
    )

# 3) تأكيد الحفظ + توليد PDF
@app.route("/smart_report/confirm", methods=["POST"])
def smart_report_confirm():
    import json as _json
    g = request.form.get

    category    = (g("category") or "").strip()
    reporter    = (g("reporter") or "admin").strip()
    date_str    = (g("date") or datetime.datetime.now().strftime("%Y-%m-%d")).strip()
    title       = (g("title") or "Smartrapport").strip()
    severity    = (g("severity") or "Middels").strip()
    status      = (g("status") or "open").strip()

    try: sections   = _json.loads(g("sections") or "[]")
    except: sections = []
    try: actions    = _json.loads(g("actions") or "[]")
    except: actions = []
    try: risk_table = _json.loads(g("risk_table") or "[]")
    except: risk_table = []

    description = (g("description") or "").strip()
    if not description and sections:
        description = "\n\n".join([f"{s.get('title','')}:\n{s.get('body','')}" for s in sections])

    if category not in UPLOAD_DIRS:
        abort(400)

    rpt = SmartReport(
        category_code=category,
        title=title,
        description=description,
        actions="",
        severity=severity,
        tags_json=_json.dumps([], ensure_ascii=False),
        suggestions_json=_json.dumps([], ensure_ascii=False),
        lang="no",
        created_by=reporter,
        status=status
    )
    db.session.add(rpt); db.session.commit()

    base_dir, pdf_name, _ = build_paths(UPLOAD_ROOT, category, rpt.id)
    os.makedirs(base_dir, exist_ok=True)
    logo_path = os.path.join(BASE_DIR, "static", "images", "logo.png")
    if not os.path.exists(logo_path): logo_path = None

    table_rows = risk_table if (isinstance(risk_table, list) and risk_table) else [
        ["Risiko", "Beskrivelse", "Tiltak"],
        [severity, "Foreløpig vurdering basert på observasjoner", "Oppfølging etter behov"]
    ]
    meta = {
        "id": rpt.id, "category_code": category, "title": title, "date": date_str,
        "created_by": reporter, "lang": "no", "severity": severity, "status": status,
        "description": description or f"Forløpig risiko: {severity}.",
        "table_rows": table_rows,
        "sections": sections,
        "actions": actions,
        "status_badge": {
            "open": ("Åpen sak", "#dc2626"),
            "processing": ("Under behandling", "#f59e0b"),
            "closed": ("Lukket", "#16a34a"),
        },
    }
    pdf_path = os.path.join(base_dir, pdf_name)
    try:
        render_pdf(pdf_path, meta, logo_path=logo_path)
    except Exception as e:
        print("[PDF ERROR]", e)
        return render_template_string(
            "<h3 style='font-family:Arial'>Feil under generering av PDF.</h3>"
            "<p>Detaljer هي مسجلة في سجلّ الخادم.</p>"
            "<p><a href='{{ url }}'>⟵ Tilbake</a></p>",
            url=url_for("smart_report_view", report_id=rpt.id),
        ), 500

    rel_pdf = os.path.join("uploads", category, "smart_reports", pdf_name).replace("\\","/")
    rpt.pdf_path = rel_pdf; rpt.html_path = None
    db.session.commit()

    return redirect(url_for("smart_report_view", report_id=rpt.id))

# 4) عرض تقرير محفوظ
@app.route("/smart_report/view/<int:report_id>")
def smart_report_view(report_id):
    rpt = SmartReport.query.get_or_404(report_id)
    data = rpt.to_dict()
    try:
        if rpt.created_at and hasattr(rpt.created_at, "strftime"):
            data["created_at"] = rpt.created_at.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return render_template("smart_report_view.html", rpt=data)

# 5) تنزيل PDF
@app.route("/smart_report/download/<int:report_id>")
def smart_report_download(report_id):
    rpt = SmartReport.query.get_or_404(report_id)
    if not rpt.pdf_path:
        abort(404)
    full_path = os.path.join(BASE_DIR, rpt.pdf_path)
    if not os.path.exists(full_path):
        abort(404)
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True)

# قائمة التقارير الذكية لفئة
@app.route("/smart_reports/<category>")
def smart_reports_list(category):
    if category not in UPLOAD_DIRS:
        abort(404)
    rows = SmartReport.query.filter_by(category_code=category)\
        .order_by(SmartReport.created_at.desc()).limit(300).all()
    items = []
    for r in rows:
        view_url = url_for("smart_report_view", report_id=r.id)
        items.append(f'<li><a href="{view_url}" target="_blank">#{r.id} — {r.title} — {r.severity}</a></li>')
    html = f"""<!doctype html><html lang="no"><head><meta charset="utf-8"><title>Smartrapporter – {category}</title>
<style>body{{font-family:Helvetica,Arial,sans-serif;padding:20px}} h1{{font-size:18px;margin-bottom:10px}} ul{{line-height:1.9}}</style></head>
<body><h1>Smartrapporter – {category}</h1><p><a href="{url_for('smart_report_new')}?category={category}">+ Ny smartrapport</a></p><ul>{''.join(items) or '<li>Ingen rapporter ennå.</li>'}</ul></body></html>"""
    return html

# ============================================================
#                 التوليد الآلي (Auto PDF)
# ============================================================
scheduler = BackgroundScheduler(daemon=True)
job_id = "auto_reports_job"

@app.route("/api/report_generate", methods=["POST"])
def api_report_generate():
    try:
        payload = request.get_json(silent=True) or {}
        category = (payload.get("category")
                    or request.form.get("category")
                    or request.args.get("category")
                    or "").strip()
        created_by = (payload.get("created_by")
                      or request.form.get("created_by")
                      or "Auto").strip()

        if not category:
            return jsonify({"ok": False, "error": "missing_category"}), 400

        if category not in UPLOAD_DIRS:
            return jsonify({"ok": False, "error": "bad_category", "hint": f"allowed={list(UPLOAD_DIRS.keys())}"}), 400

        auto_dir = os.path.join(UPLOAD_DIRS[category], "auto_reports")
        os.makedirs(auto_dir, exist_ok=True)

        logo_path = os.path.join(BASE_DIR, "static", "images", "logo.png")
        if not os.path.exists(logo_path): logo_path = None

        out_path = generate_category_report(category, UPLOAD_ROOT, logo_path=logo_path, created_by=created_by)
        if not out_path or not os.path.exists(out_path):
            return jsonify({"ok": False, "error": "no_output_from_generator"}), 500

        rel = out_path.replace(BASE_DIR, "").lstrip("\\/")
        return jsonify({"ok": True, "file": rel})

    except Exception as e:
        print("[AutoGenerate ERROR]", repr(e))
        return jsonify({"ok": False, "error": "generate_failed", "detail": str(e)}), 500

def auto_generate_selected_categories():
    with app.app_context():
        logo_path = os.path.join(BASE_DIR, "static", "images", "logo.png")
        cats_csv = (ConfigSetting.query.filter_by(key="auto_reports_categories").first()
                    or ConfigSetting(key="auto_reports_categories", value="")).value
        cats = [c for c in cats_csv.split(",") if c in UPLOAD_DIRS and c]
        for cat_code in cats:
            try:
                generate_category_report(cat_code, UPLOAD_ROOT, logo_path=logo_path, created_by="AutoScheduler")
            except Exception as e:
                print(f"[AutoReport] Error for {cat_code}: {e}")
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        obj = ConfigSetting.query.filter_by(key="auto_reports_last_run").first()
        if obj: obj.value = ts
        else: db.session.add(ConfigSetting(key="auto_reports_last_run", value=ts))
        db.session.commit()

def reschedule_auto_job():
    enabled = (ConfigSetting.query.filter_by(key="auto_reports_enabled").first()
               or ConfigSetting(key="auto_reports_enabled", value="0")).value == "1"
    wd = int((ConfigSetting.query.filter_by(key="auto_reports_weekday").first()
              or ConfigSetting(key="auto_reports_weekday", value="6")).value)
    hr = int((ConfigSetting.query.filter_by(key="auto_reports_hour").first()
              or ConfigSetting(key="auto_reports_hour", value="7")).value)
    mi = int((ConfigSetting.query.filter_by(key="auto_reports_minute").first()
              or ConfigSetting(key="auto_reports_minute", value="0")).value)
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    if enabled:
        scheduler.add_job(auto_generate_selected_categories, "cron",
                          day_of_week=str(wd), hour=hr, minute=mi, id=job_id)
        if not scheduler.running:
            scheduler.start()

@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.create_all()
        ensure_smart_reports_schema()
        seed_categories_if_needed()
        ensure_upload_dirs()
        reschedule_auto_job()
        print("DB ready, uploads ensured, scheduler loaded.")

# ========================= MANUAL REPORTS (CRUD) =========================
@app.route("/manual/<category>")
def manual_list(category):
    if category not in UPLOAD_DIRS: abort(404)
    cat = Category.query.filter_by(code=category).first_or_404()
    rows = Record.query.filter_by(category_id=cat.id).order_by(Record.created_at.desc()).all()
    return render_template("manual_list.html", category=category, rows=rows)

@app.route("/manual/<category>/new")
def manual_new(category):
    if category not in UPLOAD_DIRS: abort(404)
    return render_template("manual_form.html", category=category, rec=None)

@app.route("/manual/<category>/create", methods=["POST"])
def manual_create(category):
    if category not in UPLOAD_DIRS: abort(404)
    cat = Category.query.filter_by(code=category).first_or_404()
    title = (request.form.get("title") or "Untitled").strip()
    description = (request.form.get("description") or "").strip()
    created_by = (request.form.get("created_by") or "admin").strip()
    rec = Record(category_id=cat.id, title=title, description=description, status="open", created_by=created_by)
    db.session.add(rec); db.session.commit()
    return redirect(url_for("manual_view", rec_id=rec.id))

@app.route("/manual/rec/<int:rec_id>")
def manual_view(rec_id):
    rec = Record.query.get_or_404(rec_id)
    cat = Category.query.get(rec.category_id)
    return render_template("manual_view.html", rec=rec, category=cat.code)

@app.route("/manual/rec/<int:rec_id>/edit")
def manual_edit(rec_id):
    rec = Record.query.get_or_404(rec_id)
    cat = Category.query.get(rec.category_id)
    return render_template("manual_form.html", category=cat.code, rec=rec)

@app.route("/manual/rec/<int:rec_id>/update", methods=["POST"])
def manual_update(rec_id):
    rec = Record.query.get_or_404(rec_id)
    rec.title = (request.form.get("title") or rec.title).strip()
    rec.description = (request.form.get("description") or rec.description).strip()
    rec.status = (request.form.get("status") or rec.status).strip()
    db.session.commit()
    return redirect(url_for("manual_view", rec_id=rec.id))

@app.route("/manual/rec/<int:rec_id>/delete", methods=["POST"])
def manual_delete(rec_id):
    rec = Record.query.get_or_404(rec_id)
    db.session.delete(rec); db.session.commit()
    return redirect(url_for("manual_list", category=Category.query.get(rec.category_id).code))

@app.route("/manual/<category>/generate", methods=["POST"])
def manual_generate(category):
    if category not in UPLOAD_DIRS: abort(404)
    logo_path = os.path.join(BASE_DIR, "static", "images", "logo.png")
    out_path = generate_category_report(category, UPLOAD_ROOT, logo_path=logo_path, created_by="Manual")
    rel = out_path.replace(BASE_DIR, "").lstrip("\\/")
    return jsonify({"ok": True, "file": rel})

# ------------------ التشغيل ------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_smart_reports_schema()
        seed_categories_if_needed()
        ensure_upload_dirs()
        reschedule_auto_job()
    app.run(host="0.0.0.0", port=5000, debug=False)
