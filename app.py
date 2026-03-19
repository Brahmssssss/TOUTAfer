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
def init_db():
    try:
        # Nettoyage automatique des clés pour éviter l'erreur "Name not known"
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
        st.error(f"❌ Erreur critique de connexion : {e}")
        return None, None

sb, fb = init_db()

# --- 3. SÉCURITÉ & ROLES ---
def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def valider_mdp(username, password):
    if len(password) < 6: return False, "❌ 6 caractères minimum."
    if username.lower() == password.lower(): return False, "❌ Identifiant et mot de passe identiques."
    if not re.search(r"[A-Z]", password): return False, "❌ Il faut une MAJUSCULE."
    if not re.search(r"[a-z]", password): return False, "❌ Il faut une minuscule."
    if not re.search(r"\d", password): return False, "❌ Il faut un chiffre."
    if not re.search(r"[!@#$%^&*()]", password): return False, "❌ Il faut un caractère spécial."
    return True, ""

def log_action(user_nom, action):
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        data = {"date": now, "utilisateur": user_nom, "action": action}
        sb.table("logs").insert(data).execute()
        if fb: fb.collection("logs_backup").add(data)
    except: pass

# --- 4. ACCÈS ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    if st.button("SE CONNECTER", use_container_width=True):
        try:
            res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
            if res.data:
                st.session_state.auth = True
                st.session_state.user = res.data[0]
                log_action(st.session_state.user['nom'], "Connexion")
                st.rerun()
            else: st.error("Identifiant ou mot de passe incorrect.")
        except Exception as e: st.error(f"Erreur serveur : {e}")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Utilisateur : {user['nom']}")
    
    menu = ["📦 Stock (Tonnes)", "🛒 Vente", "💳 Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    
    choice = st.sidebar.radio("Menu", menu)

    # --- STOCK (TONNES) ---
    if choice == "📦 Stock (Tonnes)":
        st.header("État des Stocks")
        try:
            st_data = pd.DataFrame(sb.table("stock").select("*").execute().data)
            st.dataframe(st_data, use_container_width=True)
            if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
                with st.expander("📥 Ajouter arrivage"):
                    d = st.selectbox("Fer", st_data['diametre'])
                    q = st.number_input("Tonnes", min_value=0.0, format="%.3f")
                    if st.button("Ajouter"):
                        old_q = st_data.loc[st_data['diametre']==d, 'quantite'].values[0]
                        sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                        log_action(user['nom'], f"A ajouté {q}T de {d}")
                        st.rerun()
        except: st.error("Erreur de chargement.")

    # --- VENTE (CENTIMES) ---
    elif choice == "🛒 Vente":
        st.header("Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Client")
        f = col2.selectbox("Référence Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","22mm","25mm","32mm","40mm"])
        q_v = col2.number_input("Quantité (T)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = q_v * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Échéance"))
            st.warning(f"Dette : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE", use_container_width=True):
            if not cl: st.error("Nom du client obligatoire")
            else:
                try:
                    # Check Stock
                    stock_q = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                    if stock_q >= q_v:
                        data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q_v, "total": total, "paye": avance, "reste": total-avance, "echeance": date_e, "vendeur": user['nom']}
                        sb.table("ventes").insert(data_v).execute()
                        sb.table("stock").update({"quantite": stock_q - q_v}).eq("diametre", f).execute()
                        if fb: fb.collection("ventes").add(data_v)
                        st.success("Vente réussie !")
                        log_action(user['nom'], f"Vente {q_v}T de {f}")
                        st.balloons()
                    else: st.error("Stock insuffisant !")
                except Exception as e: st.error(f"Erreur : {e}")

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion du Personnel")
        empl = pd.DataFrame(sb.table("users").select("username, role, nom").execute().data)
        st.table(empl)
        
        with st.expander("➕ Créer un compte sécurisé (Style Gmail)"):
            n_n = st.text_input("Nom & Prénom")
            n_u = st.text_input("Identifiant")
            n_p = st.text_input("Mot de passe", type="password")
            roles = ["Commercial", "Comptable", "Gérant", "Patron"]
            if user['role'] in ["Développeur", "Grand Patron"]: roles.append("Grand Patron")
            n_r = st.selectbox("Rôle", roles)
            
            if st.button("Créer"):
                ok, msg = valider_mdp(n_u, n_p)
                if not ok: st.error(msg)
                else:
                    sb.table("users").insert({"username": n_u, "password": hash_pwd(n_p), "role": n_r, "nom": n_n}).execute()
                    log_action(user['nom'], f"A créé le compte {n_r} de {n_n}")
                    st.success("Compte créé !")
                    st.rerun()

    # --- CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Crédits")
        try:
            creds = pd.DataFrame(sb.table("ventes").select("*").gt("reste", 0).execute().data)
            st.dataframe(creds, use_container_width=True)
        except: st.info("Aucun crédit.")

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
