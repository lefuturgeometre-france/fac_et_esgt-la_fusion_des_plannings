from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import os
import shutil

# --- CONFIGURATION ---
dossier_telechargement = r"C:\Users\Administrateur\..."
nom_final = "ADECal.ics"  # nom du fichier permanent
nom_temp = "ADECal (1).ics"  # nom du fichier téléchargé par défaut depuis le site
url = "https://planning.univ-lemans.fr/jsp/custom/modules/plannings/anonymous_cal.jsp?resources=2975&projectId=8&calType=ical&nbWeeks=35"

# --- PRÉPARATION ---
if not os.path.exists(dossier_telechargement):
    os.makedirs(dossier_telechargement)

chemin_temp = os.path.join(dossier_telechargement, nom_temp)
chemin_final = os.path.join(dossier_telechargement, nom_final)

# Configuration Chrome
options = Options()
# options.add_argument("--headless")  # à activer si besoin
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

prefs = {
    "download.default_directory": dossier_telechargement,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(options=options)

try:
    print("-> Ouverture du site...")
    driver.get(url)

    print("⏳ Téléchargement en cours...")
    # Attente du téléchargement : boucle jusqu'à ce que le fichier apparaisse
    timeout = 15  # secondes max
    start = time.time()

    while not os.path.exists(chemin_temp):
        if time.time() - start > timeout:
            raise TimeoutError("Le fichier n’a pas été téléchargé dans le délai imparti.")
        time.sleep(1)

    print(f"✅ Nouveau fichier téléchargé : {chemin_temp}")

    # On remplace l'ancien ADECal.ics uniquement après téléchargement réussi
    if os.path.exists(chemin_final):
        os.remove(chemin_final)
        print("🗑️ Ancien ADECal.ics supprimé.")

    shutil.move(chemin_temp, chemin_final)
    print(f"💾 Nouveau fichier enregistré sous : {chemin_final}")

    # Supprime le fichier temporaire
    if os.path.exists(chemin_temp):
        os.remove(chemin_temp)
        print(f"🗑️ Fichier temporaire supprimé : {chemin_temp}")

except Exception as e:
    print(f"⚠️ Erreur : {e}")

finally:
    driver.quit()

