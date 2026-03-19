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

# --- 2. CONNEXION AUX SERVEURS (AVEC NETTOYAGE) ---
@st.cache_resource
def init_connections():
    try:
        # On récupère les secrets et on enlève les espaces invisibles (.strip())
        sb_url = st.secrets["supabase"]["url"].strip()
        sb_key = st.secrets["supabase"]["key"].strip()
        
        # Connexion Supabase
        sb = create_client(sb_url, sb_key)
        
        # Connexion Firebase (Sauvegarde de secours)
        fb = None
        if "firebase" in st.secrets:
            if not firebase_admin._apps:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            fb = firestore.client()
            
        return sb, fb
    except Exception as e:
        st.error(f"❌ Erreur de configuration des clés : {e}")
        return None, None

sb, fb = init_connections()

# --- 3. FONCTIONS DE SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def valider_securite(username, password):
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
    except:
        pass

# --- 4. INTERFACE DE CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Gestion Commerciale de Fer à Béton</p>", unsafe_allow_html=True)
    
    u_input = st.text_input("Identifiant")
    p_input = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        if sb is None:
            st.error("Les clés ne sont pas configurées. Allez dans les Secrets de Streamlit.")
        else:
            try:
                # On vérifie l'utilisateur dans Supabase
                res = sb.table("users").select("*").eq("username", u_input).eq("password", hash_pwd(p_input)).execute()
                if res.data:
                    st.session_state.auth = True
                    st.session_state.user = res.data[0]
                    log_action(st.session_state.user['nom'], "Connexion")
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except Exception as e:
                st.error(f"❌ Erreur serveur : {e}")
else:
    # --- INTERFACE PRINCIPALE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Utilisateur : {user['nom']}")
    st.sidebar.info(f"Rôle : {user['role']}")
    
    menu = ["📦 Stock (Tonnes)", "🛒 Vente", "💳 Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK ---
    if choice == "📦 Stock (Tonnes)":
        st.header("État des Stocks (en Tonnes)")
        try:
            st_data = pd.DataFrame(sb.table("stock").select("*").execute().data)
            st.dataframe(st_data, use_container_width=True)
        except:
            st.error("Erreur de chargement des stocks.")

        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter un arrivage"):
                diam = st.selectbox("Diamètre", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","22mm","25mm","32mm","40mm"])
                qte_a = st.number_input("Tonnes", min_value=0.001, format="%.3f")
                if st.button("Enregistrer l'entrée"):
                    # On récupère l'ancienne valeur
                    curr = sb.table("stock").select("quantite").eq("diametre", diam).execute().data[0]['quantite']
                    sb.table("stock").update({"quantite": curr + qte_a}).eq("diametre", diam).execute()
                    log_action(user['nom'], f"A ajouté {qte_a}T de {diam}")
                    st.success("Stock mis à jour !")
                    st.rerun()

    # --- VENTE ---
    elif choice == "🛒 Vente":
        st.header("Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Client")
        f = col2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","22mm","25mm","32mm","40mm"])
        q_v = col2.number_input("Quantité (T)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = q_v * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        if is_credit:
            avance = st.number_input("Avance (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Échéance"))
            st.warning(f"Reste : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE"):
            # Déduction Stock
            curr = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
            if curr >= q_v:
                data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q_v, "total": total, "paye": avance, "reste": total-avance, "echeance": date_e, "vendeur": user['nom']}
                sb.table("ventes").insert(data_v).execute()
                sb.table("stock").update({"quantite": curr - q_v}).eq("diametre", f).execute()
                if fb: fb.collection("ventes_backup").add(data_v)
                st.success("Vente enregistrée !")
                log_action(user['nom'], f"Vente {q_v}T de {f} à {cl}")
                st.balloons()
            else:
                st.error("Stock insuffisant !")

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion du Personnel")
        empl = pd.DataFrame(sb.table("users").select("username, role, nom").execute().data)
        st.table(empl)
        
        with st.expander("➕ Créer un compte sécurisé"):
            n_nom = st.text_input("Nom & Prénom")
            n_user = st.text_input("Identifiant")
            n_pass = st.text_input("Passe", type="password")
            roles_p = ["Commercial", "Comptable", "Gérant", "Patron"]
            if user['role'] in ["Développeur", "Grand Patron"]: roles_p.append("Grand Patron")
            n_role = st.selectbox("Rôle", roles_p)
            
            if st.button("Enregistrer"):
                v, msg = valider_securite(n_user, n_pass)
                if not v: st.error(msg)
                else:
                    sb.table("users").insert({"username": n_user, "password": hash_pwd(n_pass), "role": n_role, "nom": n_nom}).execute()
                    st.success("Compte créé !")
                    st.rerun()

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
