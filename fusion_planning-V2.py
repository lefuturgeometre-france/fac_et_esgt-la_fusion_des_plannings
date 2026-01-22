"""
fusion_planning_final_v7_timezone_strict.py
- Résout le bug de décalage (+1h hiver / +2h été).
- Force explicitement le Timezone Europe/Paris sur chaque événement.
- Utilise pytz pour une localisation précise.
"""

import re
import json
from datetime import datetime, date, time, timedelta
from icalendar import Calendar, Event, vText
from pathlib import Path
import os
import pytz # Nécessite pip install pytz

# Se placer dans le dossier du script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ---------------- CONFIG ----------------
ICS_FILE = "ADECal.ics"
JSON_FILE = "edt_IG1_complet.json"
OUTPUT_ICS = "planning_fusion.ics"
LOG_FILE = "fusion_log.txt"

# FUSEAU HORAIRE STRICT
PARIS_TZ = pytz.timezone("Europe/Paris")

# ---------------- UTILITAIRES ----------------

def make_paris_aware(dt):
    """
    Transforme n'importe quelle date (UTC, Naive, ou déjà Paris)
    en une date correctement localisée sur Europe/Paris.
    """
    if not isinstance(dt, datetime):
        # C'est une date (All day), on la laisse telle quelle
        return dt

    # Si la date n'a pas d'info de fuseau (Naive), on suppose que c'est l'heure locale (JSON)
    if dt.tzinfo is None:
        # localize gère parfaitement le passage été/hiver pour une heure locale donnée
        return PARIS_TZ.localize(dt)
    
    # Si la date a déjà un fuseau (ex: UTC venant de l'ADE), on la convertit vers Paris
    return dt.astimezone(PARIS_TZ)

def parse_json_horaire(horaire_str):
    m = re.search(r"de\s*(\d{1,2})h(\d{2})\s*à\s*(\d{1,2})h(\d{2})", horaire_str or "")
    if not m: return None, None
    h1, m1, h2, m2 = map(int, m.groups())
    return time(h1, m1), time(h2, m2)

def parse_json_date(date_str):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try: return datetime.strptime(date_str, fmt).date()
        except: continue
    return None

def normalize_text(s):
    return (s or "").strip().lower()

def clean_tokens(text):
    stopwords = {"td", "tp", "cm", "tdc", "esgt", "de", "la", "et", "le", "cours", "groupe", "l1"}
    text = normalize_text(text)
    tokens = re.findall(r"[a-zà-ÿ0-9]+", text)
    return set(t for t in tokens if t not in stopwords and len(t) > 1)

def subjects_match(title_ics, title_json):
    s1 = clean_tokens(title_ics)
    s2 = clean_tokens(title_json)
    return len(s1.intersection(s2)) > 0

def clean_menu_description(text):
    if not text: return ""
    lines = text.splitlines()
    kept_lines = []
    
    headers_blacklist = [
        "--- petit vaurouze", "--- kiosque", "sur place ou à emporter"
    ]
    exact_lines_blacklist = {
        "• pizza margherita", "• pizza 4 fromages", "• pizza poulet curry", 
        "• pizza kebab", "• pasta box", "• pasta box carbonara", 
        "• pasta box poulet curry", "• beignet", "• french touch burger boeuf", 
        "• tacos poulet curry", "• frites", "• menu non communiqué", "menu non communiqué"
    }

    for line in lines:
        original_line = line.strip()
        lower_line = original_line.lower()
        if not original_line: continue

        is_header = False
        for h in headers_blacklist:
            if h in lower_line: is_header = True; break
        if is_header: continue

        if lower_line in exact_lines_blacklist: continue
        kept_lines.append(original_line)
            
    return "\n".join(kept_lines)

def extract_prof_from_ics_description(desc):
    if not desc: return ""
    for line in desc.splitlines():
        line = line.strip()
        if len(line) <= 60 and re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", line):
            lower = line.lower()
            if "pizza" in lower or "burger" in lower: continue
            return line
    return ""

# ---------------- CHARGEMENT ----------------

p_ics = Path(ICS_FILE)
p_json = Path(JSON_FILE)
p_fusion = Path(OUTPUT_ICS)

if not p_ics.exists(): raise FileNotFoundError(f"Manque {ICS_FILE}")
if not p_json.exists(): raise FileNotFoundError(f"Manque {JSON_FILE}")

with p_ics.open("r", encoding="utf-8") as f:
    cal_ade = Calendar.from_ical(f.read())

with p_json.open("r", encoding="utf-8") as f:
    json_data = json.load(f)

# ---------------- SCAN VACANCES ----------------
vacation_days = set()
print("🏖️ Scan des vacances...")
for comp in cal_ade.walk():
    if comp.name != "VEVENT": continue
    summary = normalize_text(str(comp.get("SUMMARY", "")))
    if "vacances" in summary:
        dt = comp.get("DTSTART").dt
        # Pour les vacances, on veut juste la date, pas l'heure
        if isinstance(dt, datetime):
            d_vac = dt.date()
        else:
            d_vac = dt
        vacation_days.add(d_vac)

# ---------------- 1. HISTORIQUE (INTACT) ----------------
old_events = []
if p_fusion.exists():
    try:
        with p_fusion.open("rb") as f:
            cal_old = Calendar.from_ical(f.read())
            old_events = [c for c in cal_old.walk() if c.name == "VEVENT"]
    except: pass

today = date.today()
historique = []
print("📚 Chargement de l'historique...")

for ev in old_events:
    dt = ev.get("DTSTART").dt
    if isinstance(dt, datetime):
        d_check = dt.date()
        if d_check < today:
            historique.append(ev)

# ---------------- 2. FUTUR (FUSION + CLEAN) ----------------
json_index = {}
for idx, j in enumerate(json_data):
    d = parse_json_date(j["date"])
    start_t, end_t = parse_json_horaire(j["horaire"])
    if not d or not start_t or not end_t: continue
    
    # On indexe par date et heure locale (celle du JSON)
    key = (d, start_t.hour, start_t.minute, end_t.hour, end_t.minute)
    json_index.setdefault(key, []).append((idx, j))

log_lines = []
used_json = set()
cours_avenir = []

print("🚀 Traitement du futur (Mode Strict Paris Time)...")

for comp in cal_ade.walk():
    if comp.name != "VEVENT": continue

    summary = str(comp.get("SUMMARY", ""))
    uid = str(comp.get("UID", ""))
    location = str(comp.get("LOCATION", "") or "")
    raw_description = str(comp.get("DESCRIPTION", "") or "")
    
    # --- CONVERSION CRITIQUE ---
    # On force tout en "Europe/Paris" explicite.
    dtstart_paris = make_paris_aware(comp.get("DTSTART").dt)
    dtend_paris = make_paris_aware(comp.get("DTEND").dt)

    if isinstance(dtstart_paris, datetime):
        course_date = dtstart_paris.date()
        # On utilise l'heure locale de Paris pour la clé de recherche
        h_start, m_start = dtstart_paris.hour, dtstart_paris.minute
        h_end, m_end = dtend_paris.hour, dtend_paris.minute
    else:
        # All day event
        course_date = dtstart_paris
        h_start = m_start = h_end = m_end = 0

    if course_date < today: continue

    # --- NETTOYAGE MENU ---
    description_cleaned = clean_menu_description(raw_description)
    if course_date in vacation_days:
        if "menu" in description_cleaned.lower() or "repas" in summary.lower():
            description_cleaned = ""

    # --- FUSION ---
    key = (course_date, h_start, m_start, h_end, m_end)
    summary_norm = normalize_text(summary)
    candidates = json_index.get(key, [])
    
    match_found = False
    best_json = None
    best_idx = -1

    if candidates:
        for idx, jentry in candidates:
            if "enseignement esgt" in summary_norm:
                match_found = True; best_json = jentry; best_idx = idx; break
            if subjects_match(summary, jentry["cours"]):
                match_found = True; best_json = jentry; best_idx = idx; break
            if jentry["professeur"] and normalize_text(jentry["professeur"]) in normalize_text(raw_description):
                match_found = True; best_json = jentry; best_idx = idx; break
        
        if not match_found and len(candidates) == 1:
            match_found = True; best_json = candidates[0][1]; best_idx = candidates[0][0]

    ev = Event()
    ev.add("uid", uid)
    
    # IMPORTANT: On injecte les objets datetime qui ont tzinfo=<DstTzInfo 'Europe/Paris' ...>
    ev.add("dtstart", dtstart_paris)
    ev.add("dtend", dtend_paris)

    if match_found and best_json:
        used_json.add(best_idx)
        ev.add("summary", summary) 
        ev.add("location", best_json["salle"])
        
        desc = [f"✅ Salle mise à jour via JSON"]
        if best_json["professeur"]:
            desc.append(f"Prof (JSON) : {best_json['professeur']}")
        if description_cleaned:
             desc.append(f"{description_cleaned}")
             
        ev.add("description", "\n".join(desc))
        log_lines.append(f"MATCH: {summary} + Salle {best_json['salle']}")
    else:
        ev.add("summary", summary)
        ev.add("location", location)
        
        desc_parts = []
        if description_cleaned: desc_parts.append(description_cleaned)
        
        prof = extract_prof_from_ics_description(raw_description)
        if prof and prof not in description_cleaned: 
             desc_parts.append(f"Prof ICS: {prof}")
        
        ev.add("description", "\n".join(desc_parts))

    cours_avenir.append(ev)

# --- ORPHELINS JSON (Futur uniquement) ---
for idx, j in enumerate(json_data):
    if idx in used_json: continue
    d = parse_json_date(j["date"])
    s_t, e_t = parse_json_horaire(j["horaire"])
    if not d or d < today: continue
    
    # Création du datetime naif
    dtstart_naive = datetime.combine(d, s_t)
    dtend_naive = datetime.combine(d, e_t)
    
    # Localisation stricte vers Paris
    dtstart_paris = make_paris_aware(dtstart_naive)
    dtend_paris = make_paris_aware(dtend_naive)
    
    ev = Event()
    ev.add("uid", f"JSON-{idx}")
    ev.add("dtstart", dtstart_paris)
    ev.add("dtend", dtend_paris)
    
    # MODIFICATION ICI : Ajout du ⚠️ pour les cours orphelins
    ev.add("summary", "⚠️ " + j["cours"])
    
    ev.add("location", j["salle"])
    ev.add("description", "⚠️ Cours uniquement dans le JSON")
    cours_avenir.append(ev)

# ---------------- SAUVEGARDE ----------------
merged = Calendar()
merged.add("prodid", "-//Fusion ADE Strict//FR")
merged.add("version", "2.0")

# Note : On laisse la librairie icalendar gérer l'écriture des Timezones
# car nos objets datetime sont désormais "aware" (ils contiennent l'info Paris).
for e in historique + cours_avenir:
    merged.add_component(e)

with open(OUTPUT_ICS, "wb") as f:
    f.write(merged.to_ical())

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines))

print(f"\n✅ Terminé. {len(cours_avenir)} cours futurs traités.")
print("ℹ️ Note : Si l'import échoue sur Google, essayez de supprimer le calendrier existant et de réimporter.")
