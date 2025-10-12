# smart_report_ai.py (v2)
# -*- coding: utf-8 -*-
import math

CAT_LABELS_NO = {
    "workers":"Arbeidssikkerhet","environment":"Miljø","deviations":"Avvik","risk":"Risiko",
    "ppe":"Verneutstyr","emergency":"Beredskap","maintenance":"Vedlikehold","reports":"Rapporter"
}

LIK_VALUES = {"Svært lav":1,"Lav":2,"Middels":3,"Høy":4,"Svært høy":5}
CON_VALUES = {"Ubetydelig":1,"Liten":2,"Moderat":3,"Alvorlig":4,"Kritisk":5}

def _risk_calc(lik_label:str, con_label:str):
    L = LIK_VALUES.get(lik_label,3); C = CON_VALUES.get(con_label,3)
    score = L*C
    if score >= 16: level = "Høy"
    elif score >= 9: level = "Middels"
    else: level = "Lav"
    return score, level

def generate_norwegian_report(
    notes:str, category:str, reporter:str,
    incident_type:str="", location:str="", root_cause:str="", impact:str="",
    actions_immediate:str="", actions_corrective:str="", actions_preventive:str="",
    responsible:str="", due_date:str="",
    likelihood_label:str="Middels", consequence_label:str="Moderat"
):
    cat_label = CAT_LABELS_NO.get(category, category.capitalize() or "Rapport")
    score, severity = _risk_calc(likelihood_label, consequence_label)

    # fallback للنص الحر ضمن الوصف
    free = (notes or "").strip()
    if free:
        free = f"\n\nTilleggsnotat:\n{free}"

    text = f"""
Hendelsesrapport – {cat_label}

📍 Sted: {location or 'Ikke oppgitt'}
🧷 Hendelsestype: {incident_type or 'Ikke oppgitt'}
👤 Ansvarlig: {responsible or 'Ikke oppgitt'}   ⏰ Frist: {due_date or 'Ikke oppgitt'}

🧾 Beskrivelse og årsak:
- Rotårsak: {root_cause or 'Ikke identifisert enda'}
- Virkning/konsekvens: {impact or 'Ikke oppgitt'}{free}

🧰 Tiltak:
- Umiddelbare: {actions_immediate or 'Ingen registrert'}
- Korrigerende: {actions_corrective or 'Ingen registrert'}
- Forebyggende: {actions_preventive or 'Ingen registrert'}

🧮 Risikomatrise (før tiltak):
- Sannsynlighet: {likelihood_label}  (verdi={LIK_VALUES.get(likelihood_label,3)})
- Konsekvens: {consequence_label}    (verdi={CON_VALUES.get(consequence_label,3)})
- Skår: {score}  → Nivå: {severity}
""".strip()

    title = f"Hendelsesrapport – {cat_label}"
    table = [
        ["Risiko", "Beskrivelse", "Tiltak"],
        [severity, "Vurdering basert på matrise (S×K)", "Oppfølging iht. ansvar og frist"]
    ]

    return {
        "title": title,
        "text": text,
        "severity": severity,
        "risk_score": score,
        "table_rows": table
    }
