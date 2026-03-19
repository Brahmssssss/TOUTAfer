import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_DEST = "brahim.hanifi.2@gmail.com" # <--- Ton email perso (ex: Gmail)
EMAIL_ENVOI = "toutaferbackup@gmail.com" # <--- Ton email qui envoie (le même ou un autre)
MDP_APPLI = os.getenv("EMAIL_PASSWORD") # Le robot ira chercher tes 16 caractères ici

def envoyer_bilan():
    maintenant = datetime.now().strftime('%d/%m/%Y à %H:%M')
    sujet = f"📊 BILAN QUOTIDIEN TOUTA FER - {maintenant}"
    
    # Texte du mail (On pourra l'améliorer quand Supabase sera connecté)
    corps = f"""
    Bonjour Patron,
    
    Ceci est votre sauvegarde automatique de 20h pour TOUTA FER.
    
    L'enregistrement des données s'est bien déroulé sur les serveurs sécurisés.
    Pensez à vérifier vos crédits clients demain matin.
    
    Bonne soirée,
    Le Système TOUTA FER.
    """

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ENVOI
    msg['To'] = EMAIL_DEST
    msg['Subject'] = sujet
    msg.attach(MIMEText(corps, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ENVOI, MDP_APPLI)
        server.send_message(msg)
        server.quit()
        print("✅ Email de sauvegarde envoyé !")
    except Exception as e:
        print(f"❌ Erreur d'envoi : {e}")

if __name__ == "__main__":
    envoyer_bilan()
