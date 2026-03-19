import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime, date
from supabase import create_client # Base n°1
import firebase_admin # Base n°2 (Backup)
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- 2. CONNEXIONS AUX DEUX BASES DE DONNÉES (SUPABASE + FIREBASE) ---
@st.cache_resource
def init_connections():
    # Connexion à Supabase (Principale)
    sb_url = st.secrets["supabase"]["url"]
    sb_key = st.secrets["supabase"]["key"]
    sb = create_client(sb_url, sb_key)
    
    # Connexion à Firebase (Sauvegarde de secours)
    if not firebase_admin._apps:
        cred_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    fb = firestore.client()
    
    return sb, fb

try:
    sb, fb = init_connections()
except Exception as e:
    st.error(f"⚠️ Erreur de connexion aux serveurs : {e}")
    st.stop()

# --- 3. FONCTIONS DE SÉCURITÉ ---
def hash_pwd(password):
    """Crypte le mot de passe."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def valider_securite(username, password):
    """Règles style Gmail : 6 car, 1 Maj, 1 min, 1 chiffre, 1 spécial."""
    if len(password) < 6: return False, "❌ 6 caractères minimum."
    if username.lower() == password.lower(): return False, "❌ Identifiant et mot de passe identiques."
    if not re.search(r"[A-Z]", password): return False, "❌ Il faut une MAJUSCULE."
    if not re.search(r"[a-z]", password): return False, "❌ Il faut une minuscule."
    if not re.search(r"\d", password): return False, "❌ Il faut un chiffre."
    if not re.search(r"[!@#$%^&*()]", password): return False, "❌ Il faut un caractère spécial."
    return True, ""

def log_action(user_nom, action):
    """Enregistre chaque mouvement dans les 2 bases."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    data = {"date": now, "utilisateur": user_nom, "action": action}
    sb.table("logs").insert(data).execute()
    fb.collection("logs_backup").add(data)

# --- 4. INTERFACE DE CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Système de Gestion Immortel</h3>", unsafe_allow_html=True)
    
    u_input = st.text_input("Identifiant (ex: développeur)")
    p_input = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        # On vérifie dans la base de données Supabase
        res = sb.table("users").select("*").eq("username", u_input).eq("password", hash_pwd(p_input)).execute()
        if res.data:
            st.session_state.auth = True
            st.session_state.user = res.data[0]
            log_action(st.session_state.user['nom'], "S'est connecté")
            st.rerun()
        else:
            st.error("Identifiant ou mot de passe incorrect.")
else:
    # --- INTERFACE PRINCIPALE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Connecté : {user['nom']}")
    st.sidebar.info(f"Rôle : {user['role']}")
    st.sidebar.warning("Unité : Centimes | Poids : Tonnes")

    # Navigation selon le rôle
    menu = ["📦 Stock (Tonnes)", "🛒 Nouvelle Vente", "💳 Liste des Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique (Espion)"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- 📦 STOCK (TONNES) ---
    if choice == "📦 Stock (Tonnes)":
        st.header("📦 État des Stocks Réels")
        # Lecture en temps réel sur Supabase
        st_data = pd.DataFrame(sb.table("stock").select("*").execute().data)
        st.dataframe(st_data, use_container_width=True)
        
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter un arrivage"):
                d = st.selectbox("Diamètre du fer", st_data['diametre'])
                q = st.number_input("Nombre de Tonnes reçues", min_value=0.001, format="%.3f")
                if st.button("Confirmer l'ajout au stock"):
                    # Mise à jour Supabase + Firebase
                    sb.table("stock").update({"quantite": st_data.loc[st_data['diametre']==d, 'quantite'].values[0] + q}).eq("diametre", d).execute()
                    fb.collection("stock_backup").document(d).set({"quantite_maj": q, "date": str(date.today())})
                    log_action(user['nom'], f"A ajouté {q}T de fer {d}")
                    st.success("Stock mis à jour !")
                    st.rerun()

    # --- 🛒 VENTE (RÉACTIVITÉ TOTALE) ---
    elif choice == "🛒 Nouvelle Vente":
        st.header("🛒 Enregistrer une Vente")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom Client")
        tel = col1.text_input("Téléphone")
        f = col2.selectbox("Référence Fer", pd.DataFrame(sb.table("stock").select("diametre").execute().data))
        q_v = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix par Tonne (en Centimes)", min_value=0.0)
        
        total = q_v * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        st.divider()
        is_credit = st.checkbox("🚩 Vente à Crédit (Cocher pour crédit)")
        
        avance = total
        date_e = date.today().strftime("%d/%m/%Y")
        if is_credit:
            # S'affiche INSTANTANÉMENT
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = st.date_input("Date d'échéance du paiement").strftime("%d/%m/%Y")
            st.error(f"Reste à payer : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE DÉFINITIVEMENT", use_container_width=True):
            # Double sauvegarde immédiate
            data_v = {
                "date": date.today().strftime("%d/%m/%Y"), "client": cl, "contact": tel,
                "fer": f, "qte": q_v, "total": total, "paye": avance, "reste": total - avance,
                "echeance": date_e, "vendeur": user['nom']
            }
            # 1. Supabase
            sb.table("ventes").insert(data_v).execute()
            # 2. Firebase
            fb.collection("ventes_backup").add(data_v)
            # 3. Réduction du stock
            sb.table("stock").update({"quantite": sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite'] - q_v}).eq("diametre", f).execute()
            
            log_action(user['nom'], f"Vente à {cl} ({q_v}T de {f})")
            st.success("Vente enregistrée sur les 2 serveurs !")
            st.balloons()

    # --- 💳 CRÉDITS ---
    elif choice == "💳 Liste des Crédits":
        st.header("💳 Suivi des Dettes")
        creds = pd.DataFrame(sb.table("ventes").select("*").gt("reste", 0).execute().data)
        if creds.empty: st.info("Aucun crédit.")
        else:
            st.dataframe(creds, use_container_width=True)
            st.divider()
            id_v = st.selectbox("Sélectionner la Vente (ID)", creds['id'].tolist())
            montant = st.number_input("Montant reçu (Centimes)", min_value=0.0)
            if st.button("Valider le paiement du crédit"):
                # Mise à jour en double
                sb.table("ventes").update({"paye": creds.loc[creds['id']==id_v, 'paye'].values[0] + montant, "reste": creds.loc[creds['id']==id_v, 'reste'].values[0] - montant}).eq("id", id_v).execute()
                log_action(user['nom'], f"A reçu un paiement de crédit pour la vente {id_v}")
                st.rerun()

    # --- 👥 PERSONNEL (SÉCURITÉ ET HIÉRARCHIE) ---
    elif choice == "👥 Personnel":
        st.header("👥 Gestion des accès TOUTA FER")
        empl = pd.DataFrame(sb.table("users").select("username, role, nom").execute().data)
        st.table(empl)
        
        with st.expander("➕ Créer un compte sécurisé"):
            n_nom = st.text_input("Nom & Prénom")
            n_user = st.text_input("Identifiant")
            n_pass = st.text_input("Mot de passe", type="password")
            roles_p = ["Commercial", "Comptable", "Gérant", "Patron"]
            if user['role'] in ["Développeur", "Grand Patron"]: roles_p.append("Grand Patron")
            n_role = st.selectbox("Rôle", roles_p)
            
            if st.button("Enregistrer"):
                valide, msg = valider_securite(n_user, n_pass)
                if not valide: st.error(msg)
                else:
                    sb.table("users").insert({"username": n_user, "password": hash_pwd(n_pass), "role": n_role, "nom": n_nom}).execute()
                    log_action(user['nom'], f"A créé le compte {n_role} pour {n_nom}")
                    st.success("Compte créé avec succès !")
                    st.rerun()

        with st.expander("🗑️ Supprimer un compte"):
            if user['role'] == "Développeur":
                l_s = [u for u in empl['username'].tolist() if u != user['username']]
            elif user['role'] == "Grand Patron":
                l_s = [r['username'] for i, r in empl.iterrows() if r['role'] != 'Développeur' and r['username'] != user['username']]
            elif user['role'] == "Patron":
                l_s = [r['username'] for i, r in empl.iterrows() if r['role'] not in ['Développeur', 'Grand Patron', 'Patron']]
            else: l_s = []

            u_to_del = st.selectbox("Compte à effacer", l_s) if l_s else None
            if u_to_del and st.button("Supprimer définitivement"):
                sb.table("users").delete().eq("username", u_to_del).execute()
                log_action(user['nom'], f"A supprimé le compte de {u_to_del}")
                st.rerun()

    # --- 📜 HISTORIQUE ---
    elif choice == "📜 Historique (Espion)":
        st.header("📜 Journal de bord de TOUTA FER")
        logs = pd.DataFrame(sb.table("logs").select("*").order("id", desc=True).execute().data)
        st.dataframe(logs, use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
