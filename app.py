import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime, date
from supabase import create_client
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATION ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- CONNEXIONS ---
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
        return sb, fb
    except Exception as e:
        st.error(f"Erreur connexion : {e}")
        return None, None

sb, fb = init_db()

# --- SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    # Règle style Gmail
    if len(password) < 6: return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[!@#$%^&*()]", password): return False
    return True

# --- CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("SE CONNECTER", use_container_width=True):
        res = sb.table("users").select("*").eq("username", u).eq("password", hash_pwd(p)).execute()
        if res.data:
            st.session_state.auth = True
            st.session_state.user = res.data[0]
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect.")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"Utilisateur : {user['nom']}")
    
    menu = st.sidebar.radio("Menu", ["📦 Stock (Tonnes)", "🛒 Vente (Centimes)", "💳 Crédits", "👥 Personnel", "📜 Historique"])

    # --- STOCK ---
    if menu == "📦 Stock (Tonnes)":
        st.header("État des Stocks")
        data = sb.table("stock").select("*").execute()
        df = pd.DataFrame(data.data)
        st.dataframe(df, use_container_width=True)
        
        if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
            with st.expander("📥 Ajouter du fer"):
                d = st.selectbox("Diamètre", df['diametre'] if not df.empty else [])
                q = st.number_input("Tonnes à ajouter", min_value=0.0, format="%.3f")
                if st.button("Valider l'ajout"):
                    old_q = df.loc[df['diametre']==d, 'quantite'].values[0]
                    sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                    st.success("Stock mis à jour")
                    st.rerun()

    # --- VENTE ---
    elif menu == "🛒 Vente (Centimes)":
        st.header("Nouvelle Vente")
        c1, c2 = st.columns(2)
        cl = c1.text_input("Client")
        f = c2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","20mm","25mm","32mm","40mm"])
        q = c2.number_input("Quantité (T)", min_value=0.001, format="%.3f")
        px = c1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = q * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0)
        
        if st.button("VALIDER LA VENTE"):
            data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q, "total": total, "paye": avance, "reste": total-avance, "vendeur": user['nom']}
            sb.table("ventes").insert(data_v).execute()
            if fb: fb.collection("ventes_backup").add(data_v)
            st.success("Vente enregistrée !")
            st.balloons()

    # --- PERSONNEL ---
    elif menu == "👥 Personnel":
        st.header("Gestion Personnel")
        if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
            empl = sb.table("users").select("username, role, nom").execute()
            st.table(pd.DataFrame(empl.data))
            
            with st.expander("➕ Créer un compte"):
                n_u = st.text_input("Identifiant")
                n_p = st.text_input("Mot de passe", type="password")
                n_n = st.text_input("Nom Complet")
                n_r = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
                if st.button("Enregistrer"):
                    if valider_mdp(n_p):
                        sb.table("users").insert({"username": n_u, "password": hash_pwd(n_p), "role": n_r, "nom": n_n}).execute()
                        st.success("Compte créé !")
                        st.rerun()
                    else:
                        st.error("Mot de passe trop faible (Majuscule, chiffre, spécial requis)")

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()
