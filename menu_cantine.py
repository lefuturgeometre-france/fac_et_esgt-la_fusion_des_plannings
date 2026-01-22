import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta, time, date
import re
import os
import pytz

# --- CONFIGURATION ---
WORK_DIR = r"C:\Users\Administrateur\Desktop\Script_Hyperplanning"
ICS_FILE = os.path.join(WORK_DIR, "planning_fusion.ics")

TZ = pytz.timezone('Europe/Paris')
TODAY = datetime.now(TZ).date()

RESTAURANTS = [
    { "name": "Resto U' Vaurouzé", "url": "https://www.crous-nantes.fr/restaurant/resto-u-vaurouze/" },
    { "name": "Resto U' Bartholdi", "url": "https://www.crous-nantes.fr/restaurant/resto-u-bartholdi/" }
]

MOIS = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12
}

# --- LISTES DE FILTRAGE (BANLISTS) ---

# 1. Éléments à supprimer pour Vaurouzé (Midi et Soir)
# J'ai ajouté les variantes avec et sans parenthèses pour être sûr
VAUROUZE_GLOBAL_BANLIST = [
    "pizza margherita", "pizza 4 fromages", "pizza poulet curry", "pizza kebab",
    "pasta box", "pasta box carbonara", "pasta box poulet curry",
    "beignet", "french touch burger boeuf", "tacos poulet curry", "frites", 
    "--- kiosque ou etage (à emporter ou sur place) ---", # Ancienne version
    "--- kiosque ou etage à emporter ou sur place ---",   # NOUVELLE VERSION (SANS PARENTHÈSES)
    "--- petit vaurouze rdc sur place ou à emporter ---" 
]

# 2. Information Bartholdi
BARTHOLDI_INFO_BANLIST = [
    "--- information ---", "rappel :", "3 éléments (entrée +plat +dessert) et 1 morceau de pain",
    "pas de pichet à disposition possibilité de prendre une gourde",
    "nous n'acceptons pas la nourriture personnelle",
    "moyen de paiement est votre compte izly", "merci de votre compréhension"
]

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def get_aware_datetime(dt):
    if not isinstance(dt, datetime): dt = datetime.combine(dt, time.min)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None: return TZ.localize(dt)
    return dt.astimezone(TZ)

def parse_date(date_text):
    text = date_text.lower().replace("menu du", "").replace(",", "").strip()
    parts = text.split()
    try:
        day_index = -1
        for i, p in enumerate(parts):
            if p.isdigit() and 1 <= int(p) <= 31:
                day_index = i
                break
        if day_index == -1: return None
        day = int(parts[day_index])
        month_str = parts[day_index + 1]
        year = int(parts[day_index + 2])
        if month_str not in MOIS: return None
        return datetime(year, MOIS[month_str], day)
    except: return None

def load_calendar_data(filepath):
    busy_slots = {} 
    existing_events = []
    vacation_days = set()

    if not os.path.exists(filepath): return busy_slots, existing_events, vacation_days

    with open(filepath, 'rb') as f:
        try: cal = Calendar.from_ical(f.read())
        except: return busy_slots, existing_events, vacation_days

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary', '')).lower()
            
            # Gestion Vacances
            if "vacances" in summary:
                dtstart = component.get('dtstart').dt
                dtend = component.get('dtend').dt
                if isinstance(dtstart, datetime): start_d = dtstart.date()
                else: start_d = dtstart
                if isinstance(dtend, datetime): end_d = dtend.date()
                else: end_d = start_d + timedelta(days=1)
                
                curr = start_d
                while curr < end_d:
                    vacation_days.add(curr.strftime('%Y-%m-%d'))
                    curr += timedelta(days=1)
                existing_events.append(component)
                continue

            # Gestion Historique
            if "🍽️" in summary or "resto u'" in summary:
                dtstart = component.get('dtstart').dt
                if isinstance(dtstart, datetime):
                    event_date = dtstart.astimezone(TZ).date() if dtstart.tzinfo else dtstart.date()
                else: event_date = dtstart
                if event_date < TODAY: existing_events.append(component)
                continue
            
            # Gestion Cours
            existing_events.append(component)
            dtstart = component.get('dtstart').dt
            dtend = component.get('dtend').dt
            if not isinstance(dtstart, datetime): continue 
            dtstart = get_aware_datetime(dtstart)
            dtend = get_aware_datetime(dtend)
            day_key = dtstart.strftime('%Y-%m-%d')
            if day_key not in busy_slots: busy_slots[day_key] = []
            busy_slots[day_key].append((dtstart, dtend))

    for day in busy_slots: busy_slots[day].sort(key=lambda x: x[0])
    return busy_slots, existing_events, vacation_days

def calculate_smart_slot(date_obj, meal_type, busy_slots_today):
    if meal_type == "midi":
        open_time = TZ.localize(datetime.combine(date_obj, time(11, 0)))
        close_time = TZ.localize(datetime.combine(date_obj, time(13, 45)))
        default_start = TZ.localize(datetime.combine(date_obj, time(11, 45)))
    else:
        open_time = TZ.localize(datetime.combine(date_obj, time(18, 30)))
        close_time = TZ.localize(datetime.combine(date_obj, time(20, 0)))
        default_start = open_time 

    last_event_before = None
    first_event_after = None

    for start, end in busy_slots_today:
        if end <= close_time and end >= open_time - timedelta(hours=3): 
            if last_event_before is None or end > last_event_before: last_event_before = end
        if start >= open_time:
            if first_event_after is None or start < first_event_after: first_event_after = start

    meal_start = default_start
    if meal_type == "midi":
        if last_event_before:
            potential_start = last_event_before + timedelta(minutes=5)
            if potential_start < default_start: meal_start = default_start
            else: meal_start = potential_start
    
    if meal_start >= close_time: return None
    meal_end = meal_start + timedelta(minutes=45)
    if first_event_after:
        max_end = first_event_after - timedelta(minutes=5)
        if max_end < meal_end: meal_end = max_end

    if meal_end > close_time: meal_end = close_time
    if meal_start >= meal_end: return None
    return meal_start, meal_end

def main():
    print(f"--- Ajout Menus (Nettoyage Entête Varouzé Soir) ---")
    
    busy_slots, events_to_keep, vacation_days = load_calendar_data(ICS_FILE)
    
    cal = Calendar()
    cal.add('prodid', '-//Smart CROUS Menu//mxm.dk//')
    cal.add('version', '2.0')
    for ev in events_to_keep: cal.add_component(ev)

    headers = {'User-Agent': 'Mozilla/5.0'}
    count_added = 0

    for resto in RESTAURANTS:
        try:
            r = requests.get(resto['url'], headers=headers)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.content, 'html.parser')
            
            for menu_div in soup.find_all('div', class_='menu'):
                date_node = menu_div.find('time', class_='menu_date_title')
                if not date_node: continue
                current_date = parse_date(date_node.text)
                if not current_date: continue
                day_key = current_date.strftime('%Y-%m-%d')
                
                busy_today = busy_slots.get(day_key, [])
                
                for meal in menu_div.find_all('div', class_='meal'):
                    title_node = meal.find('div', class_='meal_title')
                    if not title_node: continue
                    meal_name = clean_text(title_node.text).lower()
                    is_dinner = "dîner" in meal_name or "diner" in meal_name or "soir" in meal_name
                    meal_type = "soir" if is_dinner else "midi"

                    foodies = meal.find('ul', class_='meal_foodies')
                    if not foodies: continue
                    
                    raw_lines = []
                    for cat in foodies.find_all('li', recursive=False):
                        cat_title = ""
                        if cat.contents: cat_title = BeautifulSoup(str(cat.contents[0]), "html.parser").get_text().strip()
                        if cat_title: raw_lines.append(f"--- {cat_title.upper()} ---")
                        for item in cat.find_all('li'):
                            it = clean_text(item.text)
                            if it: raw_lines.append(f"• {it}")

                    final_lines = []
                    stop_processing = False 
                    
                    for line in raw_lines:
                        line_lower = line.lower()
                        line_content = line.replace('•', '').strip().lower()

                        # --- RÈGLE UNIVERSELLE VAUROUZÉ ---
                        if "vaurouzé" in resto['name'].lower():
                            # Vérification stricte des éléments bannis (Entête, Pizzas, etc.)
                            if line_content in VAUROUZE_GLOBAL_BANLIST:
                                continue
                            if "petit vaurouze" in line_lower:
                                continue

                        # --- Règle Vaurouzé Midi classique ---
                        if "vaurouzé" in resto['name'].lower() and meal_type == "midi":
                            if "salle personnels administratifs" in line_lower: stop_processing = True
                        
                        if stop_processing: break

                        # --- Règle Bartholdi ---
                        if "bartholdi" in resto['name'].lower():
                            if any(b in line_lower for b in BARTHOLDI_INFO_BANLIST): continue

                        final_lines.append(line)

                    # Si vide après nettoyage, on ignore l'événement
                    real_content = [l for l in final_lines if l.startswith("•")]
                    if not real_content:
                        continue

                    # --- Création Event ---
                    slot = calculate_smart_slot(current_date, meal_type, busy_today)
                    if not slot: continue
                    
                    event = Event()
                    event.add('summary', f"🍽️ {resto['name']} ({meal_name.capitalize()})")
                    event.add('description', "\n".join(final_lines).strip())
                    event.add('location', resto['name'])
                    event.add('dtstart', slot[0])
                    event.add('dtend', slot[1])
                    event.add('uid', f"{day_key}_{resto['name'].replace(' ','')}_{meal_type}")
                    cal.add_component(event)
                    count_added += 1

        except Exception as e:
            print(f"Erreur : {e}")

    if not os.path.exists(WORK_DIR): os.makedirs(WORK_DIR)
    with open(ICS_FILE, 'wb') as f: f.write(cal.to_ical())
    print(f"\n✅ TERMINÉ : {count_added} repas ajoutés.")

if __name__ == "__main__":
    main()
