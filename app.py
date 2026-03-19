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

# --- 2. CONNEXION AVEC STATUT VISUEL ---
@st.cache_resource
def init_db():
    try:
        # Nettoyage des clés TOML
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        
        # Test de lecture réel
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
        return None, None, f"❌ Erreur de Connexion : {e}"

sb, fb, db_status = init_db()

# --- 3. FONCTIONS SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    """Vérifie : 6 car, 1 Maj, 1 min, 1 chiffre, 1 spécial."""
    if len(password) < 6: return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[!@#$%^&*()]", password): return False
    return True

# --- 4. INTERFACE DE CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    # Indicateur de statut en haut
    if "✅" in db_status:
        st.success(db_status)
    else:
        st.error(db_status)
        st.info("Vérifiez l'URL et la Clé dans les Secrets Streamlit.")

    st.markdown("<h1 style='text-align: center;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        # A. COMPTE D'URGENCE SÉCURISÉ
        if u_in == "admin" and p_in == "ToutaAdmin123!":
            st.session_state.auth = True
            st.session_state.user = {"username": "admin", "role": "Développeur", "nom": "Le Patron (Urgence)"}
            st.rerun()
            
        # B. CONNEXION NORMALE
        elif sb is not None:
            try:
                res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
                if res.data:
                    st.session_state.auth = True
                    st.session_state.user = res.data[0]
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except:
                st.error("Problème technique avec la base de données.")

else:
    # --- 5. INTERFACE PRINCIPALE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"👤 {user['nom']}")
    st.sidebar.write(f"Rôle : **{user['role']}**")
    
    menu = st.sidebar.radio("Navigation", ["📦 Stocks", "🛒 Ventes", "💳 Crédits", "👥 Personnel", "📜 Historique"])

    # --- STOCK ---
    if menu == "📦 Stocks":
        st.header("Gestion des Stocks (Tonnes)")
        try:
            res = sb.table("stock").select("*").execute()
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            
            if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
                with st.expander("📥 Ajouter un arrivage"):
                    d = st.selectbox("Référence Fer", df['diametre'].tolist())
                    q = st.number_input("Tonnes Reçues", min_value=0.0, format="%.3f")
                    if st.button("Mettre à jour le stock"):
                        old_q = df.loc[df['diametre']==d, 'quantite'].values[0]
                        sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                        st.success("Stock mis à jour !")
                        st.rerun()
        except:
            st.error("La base de données ne répond pas.")

    # --- VENTES ---
    elif menu == "🛒 Ventes":
        st.header("Nouvelle Vente (Centimes)")
        cl = st.text_input("Nom du Client")
        f = st.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q = st.number_input("Poids (Tonnes)", min_value=0.001, format="%.3f")
        px = st.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        total = q * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0)
        
        if st.button("VALIDER LA VENTE"):
            try:
                data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q, "total": total, "paye": avance, "reste": total-avance, "vendeur": user['nom']}
                sb.table("ventes").insert(data_v).execute()
                # On déduit du stock automatiquement
                q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                sb.table("stock").update({"quantite": q_act - q}).eq("diametre", f).execute()
                st.success("Vente enregistrée avec succès !")
                st.balloons()
            except:
                st.error("Erreur technique lors de l'enregistrement.")

    # --- PERSONNEL ---
    elif menu == "👥 Personnel":
        st.header("Gestion des Comptes")
        if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
            t
