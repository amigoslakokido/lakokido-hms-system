# models.py
# -*- coding: utf-8 -*-
from datetime import datetime
from database import db

# =========================
# Users
# =========================
class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(50), default="admin")
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "username": self.username, "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# =========================
# Categories
# =========================
class Category(db.Model):
    __tablename__ = "categories"
    id   = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)   # workers, deviations, ...
    name = db.Column(db.String(120), nullable=False)

    def to_dict(self):
        return {"id": self.id, "code": self.code, "name": self.name}

# =========================
# Records (generic entries per category)
# =========================
class Record(db.Model):
    __tablename__ = "records"
    id          = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status      = db.Column(db.String(20), nullable=False, default="open")  # open/closed
    created_by  = db.Column(db.String(100), default="admin")
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship("Category", backref=db.backref("records", lazy=True))

    def to_dict(self):
        return {
            "id": self.id, "category_id": self.category_id, "title": self.title,
            "description": self.description, "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# =========================
# Record Attachments
# =========================
class RecordAttachment(db.Model):
    __tablename__ = "record_attachments"
    id           = db.Column(db.Integer, primary_key=True)
    record_id    = db.Column(db.Integer, db.ForeignKey("records.id"), nullable=False)
    filename     = db.Column(db.String(255), nullable=False)
    original_name= db.Column(db.String(255), nullable=True)
    content_type = db.Column(db.String(120), nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    record = db.relationship("Record", backref=db.backref("attachments", lazy=True))

    def to_dict(self):
        return {
            "id": self.id, "record_id": self.record_id,
            "filename": self.filename, "original_name": self.original_name,
            "content_type": self.content_type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# =========================
# Config Settings (key-value)
# =========================
class ConfigSetting(db.Model):
    __tablename__ = "config_settings"
    key   = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {"key": self.key, "value": self.value}

# =========================
# GeneratedReport (التقارير اليدوية/الآلية القديمة)
# =========================
class GeneratedReport(db.Model):
    __tablename__ = "generated_reports"
    id            = db.Column(db.Integer, primary_key=True)
    category_code = db.Column(db.String(50), nullable=False)
    file_path     = db.Column(db.String(1024), nullable=False)
    created_by    = db.Column(db.String(100), default="admin")
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "category_code": self.category_code,
            "file_path": self.file_path, "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# =========================
# SmartReport (التقارير الذكية الجديدة)
# =========================
import json

class SmartReport(db.Model):
    __tablename__ = "smart_reports"
    id            = db.Column(db.Integer, primary_key=True)
    category_code = db.Column(db.String(50), nullable=False)                 # workers / deviations / ...
    title         = db.Column(db.String(255), nullable=False)                # NO
    description   = db.Column(db.Text, nullable=True)                        # NO (النص النهائي)
    actions       = db.Column(db.Text, nullable=True)                        # احتياطي
    severity      = db.Column(db.String(20), nullable=False, default="Lav")  # Lav/Middels/Høy
    status        = db.Column(db.String(20), nullable=False, default="open") # open/processing/closed
    tags_json     = db.Column(db.Text, nullable=True)                        # JSON list
    suggestions_json = db.Column(db.Text, nullable=True)                     # JSON list
    lang          = db.Column(db.String(5), nullable=False, default="no")    # ثابت نو
    created_by    = db.Column(db.String(100), nullable=False, default="admin")
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_path      = db.Column(db.String(1024), nullable=True)
    html_path     = db.Column(db.String(1024), nullable=True)

    __table_args__ = (
        db.Index("ix_smart_reports_cat_date", "category_code", "created_at"),
    )

    def to_dict(self):
        def _json_load(x):
            try:
                return json.loads(x) if x else []
            except Exception:
                return []
        return {
            "id": self.id,
            "category_code": self.category_code,
            "title": self.title,
            "description": self.description,
            "actions": self.actions,
            "severity": self.severity,
            "status": self.status,
            "tags": _json_load(self.tags_json),
            "suggestions": _json_load(self.suggestions_json),
            "lang": self.lang,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "pdf_path": self.pdf_path,
            "html_path": self.html_path,
        }

# =========================
# Seed Categories
# =========================
def seed_categories_if_needed():
    """يضمن وجود الفئات الأساسية مرة واحدة."""
    base = [
        ("reports", "Rapporter"),
        ("deviations", "Avvik"),
        ("workers", "Arbeidstakere"),
        ("environment", "Miljø"),
        ("risk", "Risiko"),
        ("ppe", "Verneutstyr"),
        ("emergency", "Beredskap"),
        ("maintenance", "Vedlikehold"),
    ]
    existing = {c.code for c in Category.query.all()}
    inserted = 0
    for code, name in base:
        if code not in existing:
            db.session.add(Category(code=code, name=name))
            inserted += 1
    if inserted:
        db.session.commit()
