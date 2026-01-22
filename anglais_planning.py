import re
import json
from datetime import datetime, date, time, timedelta
from icalendar import Calendar, Event, vText
from pathlib import Path
import os
import pytz 

# ==========================================
# CONFIGURATION DES GROUPES
# ==========================================

dates_groupe_A = [
    "17/01/2034"
]

dates_groupe_B = [
    "17/01/2034"
]

dates_groupe_online = [
    "17/01/2034"  
]

FILENAME = "planning_fusion.ics"
PARIS_TZ = pytz.timezone("Europe/Paris")

# ==========================================
# UTILITAIRES
# ==========================================

def get_event_datetime(event):
    """Récupère la date de début normalisée en timezone Paris"""
    dt = event.get('DTSTART').dt
    
    # Si c'est juste une date (pas d'heure), on la convertit
    if not isinstance(dt, datetime):
        return PARIS_TZ.localize(datetime.combine(dt, time(0, 0)))
    
    # Si c'est une datetime naive (sans timezone), on suppose Paris
    if dt.tzinfo is None:
        return PARIS_TZ.localize(dt)
    
    # Sinon on convertit vers Paris
    return dt.astimezone(PARIS_TZ)

def format_date_str(dt):
    """Formate la date pour comparaison avec les listes (JJ/MM/AAAA)"""
    return dt.strftime("%d/%m/%Y")

# ==========================================
# MAIN
# ==========================================

def main():
    if not os.path.exists(FILENAME):
        print(f"❌ Erreur : Le fichier {FILENAME} est introuvable.")
        return

    print(f"Chargement de {FILENAME} avec la librairie 'icalendar'...")

    # Lecture du fichier
    with open(FILENAME, 'r', encoding='utf-8') as f:
        cal = Calendar.from_ical(f.read())

    now = datetime.now(PARIS_TZ)
    compteur_modif = 0

    print("Traitement des cours...")

    # Parcours des composants du calendrier
    for component in cal.walk():
        if component.name == "VEVENT":
            # 1. Vérification temporelle (ne pas toucher au passé)
            dt_start = get_event_datetime(component)
            if dt_start < now:
                continue

            # 2. Récupération du titre
            summary = str(component.get('SUMMARY', '')).strip()

            # 3. Vérifier si c'est le cours d'anglais
            if summary == "TD ESGT Anglais":
                date_str = format_date_str(dt_start)
                new_summary = summary # Par défaut, ne change pas

                # Logique Groupe A
                if date_str in dates_groupe_A:
                    if not summary.endswith("GrA"):
                        new_summary = f"{summary} GrA"
                        print(f"✅ Ajout GrA pour le {date_str}")
                        compteur_modif += 1

                # Logique Groupe B
                elif date_str in dates_groupe_B:
                    if not summary.endswith("GrB"):
                        new_summary = f"{summary} GrB"
                        print(f"✅ Ajout GrB pour le {date_str}")
                        compteur_modif += 1

                # Logique Online
                elif date_str in dates_groupe_online:
                    if not summary.endswith("Online"):
                        new_summary = f"{summary} Online"
                        print(f"✅ Ajout Online pour le {date_str}")
                        compteur_modif += 1
                
                # Application de la modification
                if new_summary != summary:
                    # vText assure l'encodage correct pour le format ICS
                    component['SUMMARY'] = vText(new_summary)

    # ==========================================
    # SAUVEGARDE
    # ==========================================

    if compteur_modif > 0:
        # On écrit en binaire ('wb') car cal.to_ical() retourne des bytes
        with open(FILENAME, 'wb') as f:
            f.write(cal.to_ical())
        print(f"\n🎉 Terminé ! {compteur_modif} cours ont été modifiés.")
        print(f"Le fichier {FILENAME} a été mis à jour proprement.")
    else:
        print("\nℹ️ Aucune modification n'était nécessaire.")

if __name__ == "__main__":
    main()
