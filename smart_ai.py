# smart_ai.py
# -*- coding: utf-8 -*-
import os, json, re, time
from typing import List, Dict, Any, Tuple
from openai import OpenAI
try:
    from rag import top_k
except Exception:
    def top_k(query: str, k: int = 3):
        # احتياط: لا سياق إضافي إن تعذّر RAG
        return []
try:
    from models import HazardTemplate  # لو الجدول موجود
except Exception:
    HazardTemplate = None              # فallback إن ما كان موجود

# ===== إعداد العميل (مطلوب مفتاح) =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    # نرمي استثناء صريح بدل "ذكاء خفيف"
    raise RuntimeError("OPENAI_API_KEY is not set. Please set it before generating smart reports.")

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== ثوابت =====
SEVERITY_ENUM = ["Lav","Middels","Høy"]
STATUS_ENUM = ["open","processing","closed"]

BASE_SYSTEM_NO = """Du er en HMS-rådgiver for restaurantdrift i Norge (serveringssteder).
Skriv ALLTID på norsk (bokmål), profesjonelt، موجز ودقيق. Ikke gjenta fritekst; bygg rapport selv.
Fokuser på kjøkken, HACCP, allergener, varme arbeider, brannsikkerhet, renhold, glatte gulv, skarpe gjenstander, kjemikalier.
Struktur-krav:
- Seksjoner (i denne rekkefølgen): Sammendrag; Tema; Bakgrunn; Observasjoner; Årsaksanalyse (5 hvorfor); Risikovurdering; Tiltaksplan; Etterlevelse; Konklusjon.
- Tiltaksplan: SMART (konkret ansvar/frist/status).
- Risikovurdering: kort begrunnelse + tabell (før/etter tiltak hvis relevant).
Returner KUN JSON i henhold til skjemaet.
"""

JSON_INSTRUCTIONS = """Skjema (JSON):
{
  "title": string,
  "severity": "Lav" | "Middels" | "Høy",
  "status": "open" | "processing" | "closed",
  "sections": [{"title": string, "body": string}, ...],
  "actions": [{"tiltak": string, "ansvar": string, "frist": string, "status": string}, ...],
  "risk_table": [[string]]  // 2D-tabell. Første rad headers. Minst: ["Risiko","Beskrivelse","Tiltak"]
}
Skriv kort og konsist. Unngå generisk fyll. Oppgi kun JSON gyldig.
"""

def _clean(text:str)->str:
    t = (text or "").strip()
    t = re.sub(r"\s{2,}"," ",t)
    return t

def _hazards_context(limit:int=20)->str:
    # إذا كان عندك الجدول في models.py بنستخدمه
    if HazardTemplate is not None:
        try:
            items = HazardTemplate.query.limit(limit).all()
            if items:
                lines=[]
                for h in items:
                    acts = [a.strip() for a in (h.recommended_actions_no or "").splitlines() if a.strip()]
                    acts_str = " • ".join(acts)
                    lines.append(f"- {h.title_no}: {h.description_no}. Tiltak: {acts_str}")
                return "\n".join(lines)
        except Exception:
            pass

    # فallback ثابت للمطاعم (يعمل حتى بدون DB)
    base = [
        ("Brann-/skåldingsfare ved frityr",
         "Risiko ved håndtering av varm olje i frityrgryter, påfyll og filtrering.",
         ["Stans varmekilde ved søl", "Bruk varmebestandige hansker/forkle", "Prosedyre for filtrering/avkjøling", "Kontroller brannteppe/slokker"]),
        ("Kuttfare (kniver/utstyr)",
         "Risiko for kutt ved bruk av kniver, mandolin, food processor.",
         ["Regelmessig sliping", "Hansker kuttbestandige ved behov", "Opplæring på teknikk/ryddighet", "Vedlikehold verktøy"]),
        ("Sklirisiko (våte gulv/fett)",
         "Våte/oljete gulv i kjøkken/oppvask og lager.",
         ["Absorber søl umiddelbart", "Skilt ‘vått gulv’", "Matter antiskli og rutine renhold", "Sko arbeid antiskli"]),
        ("Allergenhåndtering",
         "Risiko feil merking/forurensing kryss mellom matvarer.",
         ["HACCP-flyt", "Oppdatere allergenliste/opplæring", "Separate redskaper/områder", "Dobbelkontroll før servering"]),
    ]
    lines=[]
    for title, desc, acts in base:
        lines.append(f"- {title}: {desc}. Tiltak: " + " • ".join(acts))
    return "\n".join(lines)

def _build_user_prompt(notes:str, category:str, reporter:str, system_code:str|None=None)->str:
    # RAG سياق من مستنداتك (إن وُجدت)
    chunks = top_k(notes or "", k=6)
    ctx = "\n---\n".join([c["text"][:1200] for c in chunks]) if chunks else "Ingen utdrag tilgjengelig."

    hz = _hazards_context()

    return f"""Kategori: {category}
System (valgfritt): {system_code or '-'}
Notater (intern, ikke vis ordrett): {notes}

Kunnskap (RAG utdrag):
{ctx}

Restaurant-hazards (lokal kunnskap):
{hz}

Krav:
- Følg seksjonsrekkefølgen obligatorisk.
- Tiltaksplan med ansvar (rolle), frist (f.eks. +7 dager), status (Planlagt/Igangsatt/Ferdig).
- Risikovurdering praktisk og relatert til kjøkkendrift.
{JSON_INSTRUCTIONS}
"""

def _validate_payload(d:Dict[str,Any])->Tuple[bool,str]:
    try:
        if not isinstance(d, dict): return False, "payload not dict"
        for key in ["title","severity","status","sections","actions"]:
            if key not in d: return False, f"missing key: {key}"
        if d["severity"] not in SEVERITY_ENUM: return False, "bad severity"
        if d["status"] not in STATUS_ENUM: return False, "bad status"
        if not isinstance(d["sections"], list) or len(d["sections"])<3: return False, "sections too short"
        if not isinstance(d.get("risk_table", []), list): return False, "risk_table not list"
        # ترتيب الأقسام
        wanted = ["Sammendrag","Tema","Bakgrunn","Observasjoner","Årsaksanalyse","Risikovurdering","Tiltaksplan","Etterlevelse","Konklusjon"]
        titles = [ (s.get("title","") or "").lower() for s in d["sections"] ]
        # بس نتحقق أن الأساسي حاضر
        for w in ["sammendrag","observasjoner","årsaksanalyse","risikovurdering","tiltaksplan","konklusjon"]:
            if not any(w in t for t in titles): return False, f"missing section: {w}"
        return True, "ok"
    except Exception as e:
        return False, str(e)

def _post_process(d:Dict[str,Any])->Dict[str,Any]:
    # تنظيف بسيط للنصوص
    for s in d.get("sections", []):
        s["body"] = _clean(s.get("body",""))
    for a in d.get("actions", []):
        a["tiltak"] = _clean(a.get("tiltak",""))
        a["ansvar"] = _clean(a.get("ansvar",""))
        a["frist"] = _clean(a.get("frist",""))
        a["status"] = _clean(a.get("status",""))
    # جدول المخاطر: ضمان رؤوس
    if not d.get("risk_table"):
        d["risk_table"] = [["Risiko","Beskrivelse","Tiltak"],
                           [d.get("severity","Middels"),"Foreløpig vurdering","Oppfølging etter behov"]]
    else:
        if isinstance(d["risk_table"], list) and d["risk_table"]:
            head = [str(x) for x in d["risk_table"][0]]
            if len(head)<3:
                d["risk_table"][0] = ["Risiko","Beskrivelse","Tiltak"]
    return d

def generate_deep_hms_report(*, notes:str, category:str, reporter:str, status:str="open", system_code:str|None=None)->Dict[str,Any]:
    notes = _clean(notes)
    user = _build_user_prompt(notes, category, reporter, system_code)

    # محاولات قليلة لإجبار JSON صحيح
    last_err = ""
    for attempt in range(2):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[{"role":"system","content":BASE_SYSTEM_NO},
                      {"role":"user","content":user}],
            response_format={"type":"json_object"}
        )
        content = resp.choices[0].message.content
        try:
            data = json.loads(content)
            ok, why = _validate_payload(data)
            if not ok:
                last_err = f"validation: {why}"
                time.sleep(0.3)
                continue
            data["status"] = status if status in STATUS_ENUM else "open"
            data = _post_process(data)
            return data
        except Exception as e:
            last_err = f"json: {e}"
            time.sleep(0.3)
            continue
    raise RuntimeError(f"Smart generation failed: {last_err}")
