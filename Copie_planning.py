import shutil
import os
from datetime import datetime

def copier_fichier_ics():
    # Nom du fichier principal
    nom_fichier = "planning_fusion.ics"

    # Répertoire source (même dossier que le script)
    dossier_source = os.path.dirname(os.path.abspath(__file__))

    # Répertoire de destination principal
    dossier_destination = r"C:....."

    # Dossier d'archive (dans le même répertoire que le script)
    dossier_archive = os.path.join(dossier_source, "Archive_planning")

    # Chemins complets
    source = os.path.join(dossier_source, nom_fichier)
    destination = os.path.join(dossier_destination, nom_fichier)

    try:
        # Vérifie que le fichier source existe
        if not os.path.exists(source):
            print(f"❌ Le fichier {nom_fichier} est introuvable dans {dossier_source}")
            return

        # --- 1️⃣ Copie principale vers wwwroot ---
        shutil.copy2(source, destination)
        print(f"✅ Fichier copié avec succès vers : {destination}")

        # --- 2️⃣ Copie d'archive avec date et heure ---
        # Crée le dossier d'archive s'il n'existe pas
        os.makedirs(dossier_archive, exist_ok=True)

        # Format de la date pour le nom du fichier
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nom_archive = f"planning_fusion_{date_str}.ics"
        destination_archive = os.path.join(dossier_archive, nom_archive)

        shutil.copy2(source, destination_archive)
        print(f"📦 Copie d’archive créée : {destination_archive}")

    except PermissionError:
        print("⚠️ Erreur : Permission refusée. Exécute le script en tant qu’administrateur.")
    except Exception as e:
        print(f"⚠️ Une erreur est survenue : {e}")

if __name__ == "__main__":
    copier_fichier_ics()
