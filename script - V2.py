
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import os
import re
from datetime import datetime

current_year_global = None
last_month_global = None


save_path = r"C:\Users\Administrateur\....edt_IG1_complet.json"

options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--start-maximized")


driver = webdriver.Chrome(options=options)

jours_map = {
    -1: "Lundi",
    304: "Mardi",
    609: "Mercredi",
    914: "Jeudi",
    1219: "Vendredi"
}

jours_ordres = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]

def trouver_jour(style):
    match = re.search(r"left:\s*(-?\d+)px", style)
    if match:
        print(match)
        left_val = int(match.group(1))
        for val, jour in jours_map.items():
            if abs(left_val - val) <= 15:
                return jour
    return "Inconnu"

def lire_dates_semaine():
    global current_year_global, last_month_global

    dates = {}
    try:
        titres = driver.find_elements(By.CSS_SELECTOR, "div[id^='id_38_titreTranche']")

        if current_year_global is None:
            current_year_global = datetime.now().year
            last_month_global = None

        for titre in titres:
            txt = titre.text.strip().replace("\n", " ")
            if not txt:
                continue

            m = re.search(r"(\d{1,2})\s+([a-zéû]+)", txt, re.I)
            if not m:
                continue

            jour_num, mois_txt = m.groups()
            mois_map = {
                "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
                "juillet": 7, "août": 8, "septembre": 9, "octobre": 10,
                "novembre": 11, "décembre": 12
            }

            mois_num = mois_map.get(mois_txt.lower())
            if mois_num is None:
                continue

            # ✅ passage décembre → janvier (UNE SEULE FOIS)
            if last_month_global is not None and mois_num < last_month_global:
                current_year_global += 1

            last_month_global = mois_num

            date_obj = datetime(current_year_global, mois_num, int(jour_num))

            jour_nom = titre.text.split('.')[0].capitalize()
            jour_complet = next(
                (j for j in jours_ordres if j.lower().startswith(jour_nom.lower())),
                jour_nom
            )

            dates[jour_complet] = date_obj.strftime("%Y-%m-%d")

        print("Dates détectées pour la semaine :", dates)

    except Exception as e:
        print("⚠️ Erreur lors de la lecture des dates :", e)

    return dates



def extraire_cours_pour_semaine(edt_list, semaine_num):
    """Extrait les cours de la semaine affichée"""
    body = driver.find_element(By.TAG_NAME, "body")
    for _ in range(6):
        ActionChains(driver).move_to_element(body).send_keys(Keys.PAGE_DOWN).perform()
        time.sleep(1.0)

    dates_jours = lire_dates_semaine()

    cours_elements = driver.find_elements(By.CSS_SELECTOR, "div.EmploiDuTemps_Element")
    print(f"-> {len(cours_elements)} blocs détectés pour la semaine {semaine_num}")

    for bloc in cours_elements:
        try:
            cours_simple = bloc.find_element(By.CSS_SELECTOR, "div.cours-simple")
            horaire = cours_simple.get_attribute("title").strip()
            style = bloc.get_attribute("style")
            jour = trouver_jour(style)
            contenus = cours_simple.find_elements(By.CSS_SELECTOR, "div.contenu")
            labels = cours_simple.find_elements(By.TAG_NAME, "label")

            nom_cours = labels[0].text.strip() if labels else ""
            prof = ""
            salle = ""

            for c in contenus:
                txt = c.text.strip()
                if not txt or txt == nom_cours:
                    continue
                if re.search(r"\b(Salle|Amphi)\b", txt, re.I):
                    salle = txt
                elif not prof:
                    prof = txt

            date_du_jour = dates_jours.get(jour, "")

            edt_list.append({
                "semaine": semaine_num,
                "jour": jour,
                "date": date_du_jour,
                "horaire": horaire,
                "cours": nom_cours,
                "professeur": prof,
                "salle": salle
            })

        except Exception:
            continue


try:
    print("-> Ouverture du site...")
    driver.get("https://hpesgt.cnam.fr/hp/invite")
    time.sleep(5)

    print("-> Sélection de la classe IG1...")
    champ = driver.find_element(By.ID, "GInterface.Instances[1].Instances[1].bouton_Edit")
    champ.clear()
    champ.send_keys("IG1")
    time.sleep(1)
    champ.send_keys(Keys.ENTER)
    time.sleep(5)

    edt_total = []

    cal_div = driver.find_element(By.ID, "GInterface.Instances[1].Instances[3]_Div_Calendrier")

    N_SEMAINES = 8
    for i in range(N_SEMAINES):
        print(f"\n=== Récupération de la semaine {i+1}/{N_SEMAINES} ===")
        extraire_cours_pour_semaine(edt_total, i+1)

        if i < N_SEMAINES - 1:
            try:
                cal_div.send_keys(Keys.ARROW_RIGHT)
                print("→ Passage à la semaine suivante...")
                time.sleep(4)
            except Exception:
                print("⚠️ ARROW_RIGHT échoué, tentative via body")
                try:
                    body = driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.ARROW_RIGHT)
                    time.sleep(4)
                except Exception as e:
                    print("Échec du changement de semaine :", e)

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(edt_total, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Données enregistrées pour {N_SEMAINES} semaines dans : {save_path}")

finally:
    driver.quit()
