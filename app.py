import streamlit as st
import pandas as pd
import hashlib
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
from datetime import datetime, date
from supabase import create_client
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- 2. CONNEXIONS ---
@st.cache_resource
def init_db():
    try:
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        fb = None
        if "firebase" in st.secrets:
            if not firebase_admin._apps:
                cred = credentials.Certificate(dict(st.secrets["firebase"]))
                firebase_admin.initialize_app(cred)
            fb = firestore.client()
        return sb, fb, "✅ Serveur Connecté"
    except Exception as e:
        return None, None, f"❌ Déconnecté : {e}"

sb, fb, db_status = init_db()

# --- 3. FONCTIONS SÉCURITÉ & MAIL ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    if len(password) < 6: return False, "❌ 6 caractères min."
    if not re.search(r"[A-Z]", password): return False, "❌ MAJUSCULE requise."
    if not re.search(r"\d", password): return False, "❌ Chiffre requis."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>/\-_]", password): return False, "❌ Symbole requis."
    return True, ""

def log_action(user_nom, action):
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        data = {"date": now, "utilisateur": user_nom, "action": action}
        sb.table("logs").insert(data).execute()
        if fb: fb.collection("logs_backup").add(data)
    except: pass

def envoyer_sauvegarde_mail(user_nom):
    try:
        # 1. Récupération des données
        s = pd.DataFrame(sb.table("stock").select("*").execute().data)
        v = pd.DataFrame(sb.table("ventes").select("*").execute().data)
        l = pd.DataFrame(sb.table("logs").select("*").execute().data)

        # 2. Création du fichier Excel en mémoire
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            s.to_excel(writer, sheet_name='Stocks', index=False)
            v.to_excel(writer, sheet_name='Ventes_Credits', index=False)
            l.to_excel(writer, sheet_name='Historique', index=False)
        excel_data = output.getvalue()

        # 3. Configuration Mail
        msg = MIMEMultipart()
        msg['Subject'] = f"📊 SAUVEGARDE MANUELLE TOUTA FER - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        msg['From'] = st.secrets["gmail"]["email_envoi"]
        msg['To'] = st.secrets["gmail"]["email_dest"]
        msg.attach(MIMEText(f"Bonjour, voici la sauvegarde demandée par {user_nom}."))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(excel_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=Sauvegarde_TOUTA_FER.xlsx")
        msg.attach(part)

        # 4. Envoi
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(st.secrets["gmail"]["email_envoi"], st.secrets["gmail"]["mdp_appli"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return str(e)

# --- 4. CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown(f"<p style='text-align:center;'>Statut : {db_status}</p>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        if u_in == "admin" and p_in == "ToutaAdmin123!":
            st.session_state.auth = True
            st.session_state.user = {"username":"admin", "role":"Développeur", "nom":"Le Patron"}
            st.rerun()
        elif sb:
            res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
            if res.data:
                st.session_state.auth = True
                st.session_state.user = res.data[0]
                log_action(st.session_state.user['nom'], "Connexion")
                st.rerun()
            else: st.error("Identifiant ou mot de passe incorrect.")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"👤 **{user['nom']}**")
    
    # --- BOUTON SAUVEGARDE (PATRONS UNIQUEMENT) ---
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        st.sidebar.divider()
        if st.sidebar.button("📧 Envoyer Sauvegarde Mail"):
            with st.spinner("Envoi en cours..."):
                res_mail = envoyer_sauvegarde_mail(user['nom'])
                if res_mail == True: st.sidebar.success("✅ Mail envoyé !")
                else: st.sidebar.error(f"❌ Erreur : {res_mail}")

    menu = st.sidebar.radio("Navigation", ["📦 Stocks", "🛒 Ventes", "💳 Crédits", "👥 Personnel", "📜 Historique"])

    # --- VENTES (AVEC CONTACT CLIENT) ---
    if choice == "🛒 Ventes":
        st.header("Nouvelle Vente")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom du Client")
        tel = col1.text_input("Contact (Tél / Email)") # AJOUT CONTACT
        f = col2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q = col2.number_input("Quantité (Tonnes)", min_value=0.0, format="%.3f")
        px = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = q * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            st.date_input("Échéance")

        if st.button("🚀 VALIDER LA VENTE"):
            try:
                q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                if q_act >= q:
                    data_v = {"date": str(date.today()), "client": cl, "contact": tel, "fer": f, "qte": q, "total": total, "paye": avance, "reste": total-avance, "vendeur": user['nom']}
                    sb.table("ventes").insert(data_v).execute()
                    sb.table("stock").update({"quantite": q_act - q}).eq("diametre", f).execute()
                    if fb: fb.collection("ventes_backup").add(data_v)
                    log_action(user['nom'], f"Vente {q}T de {f} à {cl}")
                    st.success("Vente enregistrée !")
                    st.balloons()
                else: st.error("Stock insuffisant")
            except: st.error("Erreur")

    # --- STOCK ---
    elif choice == "📦 Stocks":
        st.header("État des Stocks")
        res = sb.table("stock").select("*").execute()
        df_s = pd.DataFrame(res.data)
        st.dataframe(df_s, use_container_width=True)
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter arrivage"):
                d = st.selectbox("Référence", df_s['diametre'].tolist())
                tonnes = st.number_input("Tonnes", min_value=0.0)
                if st.button("Ajouter"):
                    old = df_s.loc[df_s['diametre']==d, 'quantite'].values[0]
                    sb.table("stock").update({"quantite": old + tonnes}).eq("diametre", d).execute()
                    log_action(user['nom'], f"Ajout {tonnes}T de {d}")
                    st.rerun()

    # --- CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Dettes")
        res_v = sb.table("ventes").select("*").gt("reste", 0).execute()
        if res_v.data:
            df_c = pd.DataFrame(res_v.data)
            st.dataframe(df_c, use_container_width=True)
        else: st.info("Aucun crédit")

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion Personnel")
        res_u = sb.table("users").select("*").execute()
        st.table(pd.DataFrame(res_u.data)[['username', 'role', 'nom']])
        with st.expander("➕ Créer"):
            nu, np, nn = st.text_input("Identifiant"), st.text_input("Pass", type="password"), st.text_input("Nom")
            nr = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
            if st.button("Créer"):
                ok, msg = valider_mdp(np)
                if ok:
                    sb.table("users").insert({"username": nu, "password": hash_pwd(np), "role": nr, "nom": nn}).execute()
                    st.rerun()
                else: st.error(msg)

    # --- HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("Historique")
        res_l = sb.table("logs").select("*").order("id", desc=True).execute()
        st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
