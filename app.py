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

# --- 2. CONNEXIONS BASES DE DONNÉES ---
@st.cache_resource
def init_db():
    try:
        # Nettoyage des clés pour éviter les erreurs d'espaces
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        
        # Test de connexion
        sb.table("stock").select("count", count="exact").execute()
        
        fb = None
        if "firebase" in st.secrets:
            if not firebase_admin._apps:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            fb = firestore.client()
        return sb, fb, "✅ Serveur Connecté"
    except Exception as e:
        return None, None, f"❌ Erreur Connexion : {e}"

sb, fb, db_status = init_db()

# --- 3. FONCTIONS SÉCURITÉ & MAIL ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    if len(password) < 6: return False, "❌ 6 caractères min."
    if not re.search(r"[A-Z]", password): return False, "❌ MAJUSCULE requise."
    if not re.search(r"[a-z]", password): return False, "❌ minuscule requise."
    if not re.search(r"\d", password): return False, "❌ Chiffre requis."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>/\-_]", password): return False, "❌ Caractère spécial requis (./@! etc)."
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
        s = pd.DataFrame(sb.table("stock").select("*").execute().data)
        v = pd.DataFrame(sb.table("ventes").select("*").execute().data)
        l = pd.DataFrame(sb.table("logs").select("*").execute().data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            s.to_excel(writer, sheet_name='Stocks', index=False)
            v.to_excel(writer, sheet_name='Ventes_Credits', index=False)
            l.to_excel(writer, sheet_name='Historique', index=False)
        
        msg = MIMEMultipart()
        msg['Subject'] = f"📊 SAUVEGARDE TOUTA FER - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        msg['From'] = st.secrets["gmail"]["email_envoi"]
        msg['To'] = st.secrets["gmail"]["email_dest"]
        msg.attach(MIMEText(f"Bilan demandé par {user_nom}."))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(output.getvalue())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment; filename=Sauvegarde_TOUTA_FER.xlsx")
        msg.attach(part)

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
    st.info(db_status)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        if u_in == "admin" and p_in == "ToutaAdmin123!":
            st.session_state.auth = True
            st.session_state.user = {"username":"admin", "role":"Développeur", "nom":"Patron Maître"}
            st.rerun()
        elif sb:
            res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
            if res.data:
                st.session_state.auth = True
                st.session_state.user = res.data[0]
                st.rerun()
            else: st.error("Identifiant ou mot de passe incorrect.")
else:
    # --- 5. INTERFACE PRINCIPALE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"👤 {user['nom']} ({user['role']})")
    
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        if st.sidebar.button("📧 Envoyer Sauvegarde Mail"):
            res_m = envoyer_sauvegarde_mail(user['nom'])
            if res_m == True: st.sidebar.success("✅ Envoyé !")
            else: st.sidebar.error(f"❌ Erreur mail")

    # Correction ici : La variable 'choice' est bien définie
    choice = st.sidebar.radio("Navigation", ["📦 Stocks", "🛒 Ventes", "💳 Crédits", "👥 Personnel", "📜 Historique"])

    # --- STOCKS ---
    if choice == "📦 Stocks":
        st.header("État des Stocks (Tonnes)")
        res_s = sb.table("stock").select("*").execute()
        df_s = pd.DataFrame(res_s.data).sort_values('diametre')
        st.dataframe(df_s, use_container_width=True)
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter arrivage"):
                d = st.selectbox("Fer", df_s['diametre'].tolist())
                q = st.number_input("Tonnes", min_value=0.0, format="%.3f")
                if st.button("Valider"):
                    old = df_s.loc[df_s['diametre']==d, 'quantite'].values[0]
                    sb.table("stock").update({"quantite": old + q}).eq("diametre", d).execute()
                    log_action(user['nom'], f"Arrivage {q}T de {d}")
                    st.rerun()

    # --- VENTES ---
    elif choice == "🛒 Ventes":
        st.header("Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Client")
        tel = col1.text_input("Contact (Tél/Email)")
        f = col2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q_v = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        total = q_v * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Échéance"))

        if st.button("🚀 VALIDER LA VENTE"):
            q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
            if q_act >= q_v:
                dv = {"date":str(date.today()), "client":cl, "contact":tel, "fer":f, "qte":q_v, "total":total, "paye":avance, "reste":total-avance, "echeance":date_e, "vendeur":user['nom']}
                sb.table("ventes").insert(dv).execute()
                sb.table("stock").update({"quantite": q_act - q_v}).eq("diametre", f).execute()
                if fb: fb.collection("ventes_backup").add(dv)
                log_action(user['nom'], f"Vente {q_v}T de {f} à {cl}")
                st.success("Vente réussie !")
                st.balloons()
            else: st.error("Stock insuffisant")

    # --- CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Crédits")
        res_v = sb.table("ventes").select("*").gt("reste", 0).execute()
        if res_v.data:
            df_c = pd.DataFrame(res_v.data)
            st.dataframe(df_c, use_container_width=True)
            id_sel = st.selectbox("ID Vente", df_c['id'].tolist())
            mnt = st.number_input("Montant reçu (Centimes)", min_value=0.0)
            if st.button("Encaisser"):
                v_sel = df_c[df_c['id']==id_sel].iloc[0]
                sb.table("ventes").update({"paye":v_sel['paye']+mnt, "reste":v_sel['reste']-mnt}).eq("id", id_sel).execute()
                log_action(user['nom'], f"Paiement {mnt} de {v_sel['client']}")
                st.rerun()
        else: st.info("Aucun crédit")

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion Personnel")
        res_u = sb.table("users").select("*").execute()
        df_u = pd.DataFrame(res_u.data)
        st.table(df_u[['username', 'role', 'nom']])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Créer")
            nu, np, nn = st.text_input("Identifiant"), st.text_input("Passe", type="password"), st.text_input("Nom")
            nr = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
            if st.button("Créer"):
                ok, msg = valider_mdp(np)
                if ok:
                    sb.table("users").insert({"username":nu, "password":hash_pwd(np), "role":nr, "nom":nn}).execute()
                    st.rerun()
                else: st.error(msg)
        with col2:
            st.subheader("🗑️ Supprimer")
            if user['role'] == "Développeur": l_s = df_u['username'].tolist()
            elif user['role'] == "Grand Patron": l_s = df_u[df_u['role']!='Développeur']['username'].tolist()
            else: l_s = df_u[~df_u['role'].isin(['Développeur','Grand Patron','Patron'])]['username'].tolist()
            u_del = st.selectbox("Compte", [u for u in l_s if u != user['username']])
            if u_del and st.button("Supprimer définitivement"):
                sb.table("users").delete().eq("username", u_del).execute()
                st.rerun()

    # --- HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("Historique Audit")
        res_l = sb.table("logs").select("*").order("id", desc=True).execute()
        st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
