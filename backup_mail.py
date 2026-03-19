import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime

# --- CONFIGURATION ---
EMAIL_DEST = "TON_EMAIL_A_TOI@gmail.com" # <--- Mets ton email ici
EMAIL_ENVOI = "TON_EMAIL_ENTREPRISE@gmail.com" # <--- L'email qui envoie
MDP_APPLI = os.getenv("EMAIL_PASSWORD") # Récupéré de GitHub Secrets

def envoyer_backup():
    sujet = f"📊 Bilan Quotidien TOUTA FER - {datetime.now().strftime('%d/%m/%Y')}"
    corps = "Bonjour Patron, voici la sauvegarde automatique de vos stocks et ventes de ce soir."

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ENVOI
    msg['To'] = EMAIL_DEST
    msg['Subject'] = sujet
    msg.attach(MIMEText(corps, 'plain'))

    # Ici, le script ira chercher tes données dans Supabase 
    # et créera un fichier Excel en pièce jointe (On le configurera avec Supabase)
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ENVOI, MDP_APPLI)
        server.send_message(msg)
        server.quit()
        print("✅ Email envoyé avec succès !")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    envoyer_backup()
