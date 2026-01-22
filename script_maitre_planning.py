import subprocess
import time
import os

def lancer_script(nom_script):
    """Lance un script Python situé dans le même dossier."""
    chemin_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), nom_script)
    
    if not os.path.exists(chemin_script):
        print(f"❌ Le fichier {nom_script} est introuvable.")
        return False
    
    print(f"▶️ Exécution de {nom_script} ...")
    try:
        subprocess.run(["python", chemin_script], check=True)
        print(f"✅ {nom_script} terminé avec succès.\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Erreur lors de l’exécution de {nom_script} : {e}")
        return False

if __name__ == "__main__":
    print("🚀 Lancement automatique de la suite des scripts...\n")

    # 1️⃣ script-V2.py
    if lancer_script("script - V2.py"):
        print("⏳ Attente de 5 secondes avant la prochaine étape...")
        time.sleep(10)

        if lancer_script("script_planning_fac.py"):
            print("⏳ Attente de 5 secondes avant la copie du planning...")
            time.sleep(10)

        # 2️⃣ fusion_planning-V2.py
            if lancer_script("fusion_planning-V2.py"):
                print("⏳ Attente de 10 secondes avant la copie du planning...")
                time.sleep(10)

                if lancer_script("menu_cantine.py"):
                    print("⏳ Attente de 10 secondes avant la copie du planning...")
                    time.sleep(10)

                # 3️⃣ Copie_planning.py
                    lancer_script("anglais_planning.py")
                    lancer_script("Copie_planning.py")

    print("\n🏁 Exécution complète terminée.")
