import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime, date
from supabase import create_client
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- 2. CONNEXIONS SÉCURISÉES ---
@st.cache_resource
def init_connections():
    try:
        # On récupère et on NETTOIE les clés (enlève les espaces et retours à la ligne)
        sb_url = st.secrets["supabase"]["url"].strip()
        sb_key = st.secrets["supabase"]["key"].strip()
        
        # Connexion Supabase
        sb = create_client(sb_url, sb_key)
        
        # Connexion Firebase (Optionnelle pour ne pas bloquer l'appli)
        fb = None
        if "firebase" in st.secrets:
            if not firebase_admin._apps:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            fb = firestore.client()
            
        return sb, fb
    except Exception as e:
        st.error(f"❌ Erreur de connexion : {e}")
        return None, None

sb, fb = init_connections()

# --- 3. FONCTIONS DE SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 4. INTERFACE DE CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    
    u_input = st.text_input("Identifiant")
    p_input = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        if sb is None:
            st.error("Le serveur Supabase est injoignable. Vérifiez vos Secrets Streamlit.")
        else:
            try:
                # Vérification dans Supabase
                res = sb.table("users").select("*").eq("username", u_input).eq("password", hash_pwd(p_input)).execute()
                if res.data:
                    st.session_state.auth = True
                    st.session_state.user = res.data[0]
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except Exception as e:
                st.error(f"Erreur lors de la recherche de l'utilisateur : {e}")
else:
    # --- INTERFACE UNE FOIS CONNECTÉ ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Vendeur : {user['nom']}")
    
    menu = ["📦 Stock", "🛒 Vente", "💳 Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    
    choice = st.sidebar.radio("Menu", menu)

    # --- LOGIQUE STOCK ---
    if choice == "📦 Stock":
        st.header("📦 État des Stocks (Tonnes)")
        try:
            st_data = pd.DataFrame(sb.table("stock").select("*").execute().data)
            st.dataframe(st_data, use_container_width=True)
        except:
            st.error("Impossible de charger les stocks.")

    # --- LOGIQUE VENTE ---
    elif choice == "🛒 Vente":
        st.header("🛒 Nouvelle Vente (Centimes)")
        cl = st.text_input("Client")
        f = st.selectbox("Diamètre", ["6mm","8mm","10mm","12mm","14mm","16mm","20mm","25mm","32mm","40mm"])
        q = st.number_input("Tonnes", min_value=0.001, format="%.3f")
        px = st.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = q * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        if is_credit:
            avance = st.number_input("Avance (Centimes)", min_value=0.0)
        
        if st.button("🚀 VALIDER"):
            data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q, "total": total, "paye": avance, "reste": total-avance, "vendeur": user['nom']}
            try:
                sb.table("ventes").insert(data_v).execute()
                if fb: fb.collection("ventes").add(data_v)
                st.success("Vente enregistrée !")
                st.balloons()
            except Exception as e:
                st.error(f"Erreur d'enregistrement : {e}")

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
