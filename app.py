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

# --- 2. DIAGNOSTIC DU FICHIER TOML (SECRETS) ---
def check_secrets():
    status = True
    if "supabase" not in st.secrets:
        st.error("❌ Erreur TOML : Section [supabase] manquante.")
        status = False
    if "firebase" not in st.secrets:
        st.warning("⚠️ Attention TOML : Section [firebase] manquante (Backup désactivé).")
    return status

# --- 3. CONNEXIONS SÉCURISÉES ---
@st.cache_resource
def init_db():
    try:
        # Nettoyage automatique des clés
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
        return None, None

# Lancement du diagnostic et de la connexion
if check_secrets():
    sb, fb = init_db()
else:
    st.stop()

# --- 4. FONCTIONS DE SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    # Règle style Gmail : 6 car, 1 Maj, 1 min, 1 chiffre, 1 spécial
    if len(password) < 6: return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"\d", password): return False
    if not re.search(r"[!@#$%^&*()]", password): return False
    return True

def log_action(user_nom, action):
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        data = {"date": now, "utilisateur": user_nom, "action": action}
        sb.table("logs").insert(data).execute()
        if fb: fb.collection("logs_backup").add(data)
    except: pass

# --- 5. INTERFACE DE CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        # --- A. COMPTE ADMIN D'URGENCE (HARDCODÉ) ---
        if u_in == "admin" and p_in == "admin123":
            st.session_state.auth = True
            st.session_state.user = {"username": "admin", "role": "Développeur", "nom": "Administrateur"}
            st.rerun()
            
        # --- B. CONNEXION VIA SUPABASE ---
        elif sb is not None:
            try:
                res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
                if res.data:
                    st.session_state.auth = True
                    st.session_state.user = res.data[0]
                    log_action(st.session_state.user['nom'], "Connexion")
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
            except Exception as e:
                st.error(f"Erreur serveur : {e}")
        else:
            st.error("Connexion impossible. Vérifiez vos clés dans les Secrets.")

else:
    # --- 6. INTERFACE PRINCIPALE (APRÈS CONNEXION) ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Utilisateur : {user['nom']}")
    st.sidebar.info(f"Rôle : {user['role']}")
    
    menu = ["📦 Stock (Tonnes)", "🛒 Vente", "💳 Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- ONGLET STOCK ---
    if choice == "📦 Stock (Tonnes)":
        st.header("📦 État des Stocks")
        try:
            res = sb.table("stock").select("*").execute()
            df = pd.DataFrame(res.data)
            st.dataframe(df, use_container_width=True)
            
            if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
                with st.expander("📥 Ajouter du Fer (Arrivage)"):
                    d = st.selectbox("Diamètre", df['diametre'].tolist() if not df.empty else [])
                    q = st.number_input("Tonnes", min_value=0.0, format="%.3f")
                    if st.button("Valider l'ajout"):
                        old_q = df.loc[df['diametre']==d, 'quantite'].values[0]
                        sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                        log_action(user['nom'], f"A ajouté {q}T de {d}")
                        st.success("Stock mis à jour !")
                        st.rerun()
        except:
            st.error("Erreur de lecture de la base Supabase.")

    # --- ONGLET VENTE (RÉACTIF) ---
    elif choice == "🛒 Vente":
        st.header("🛒 Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom du Client")
        f = col2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q_v = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix / Tonne (en Centimes)", min_value=0.0)
        
        total = q_v * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Échéance du crédit"))
            st.warning(f"Reste à payer : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE", use_container_width=True):
            if not cl: st.error("Le nom du client est obligatoire.")
            else:
                try:
                    # On vérifie et retire du stock
                    q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                    if q_act >= q_v:
                        data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q_v, "total": total, "paye": avance, "reste": total-avance, "echeance": date_e, "vendeur": user['nom']}
                        sb.table("ventes").insert(data_v).execute()
                        sb.table("stock").update({"quantite": q_act - q_v}).eq("diametre", f).execute()
                        if fb: fb.collection("ventes_backup").add(data_v)
                        st.success("Vente enregistrée avec succès !")
                        log_action(user['nom'], f"Vente de {q_v}T de {f} à {cl}")
                        st.balloons()
                    else:
                        st.error("Stock insuffisant !")
                except Exception as e:
                    st.error(f"Erreur d'enregistrement : {e}")

    # --- ONGLET PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("👥 Gestion du Personnel")
        try:
            res = sb.table("users").select("username, role, nom").execute()
            st.table(pd.DataFrame(res.data))
            
            with st.expander("➕ Créer un compte employé"):
                n_u = st.text_input("Identifiant (Login)")
                n_p = st.text_input("Mot de passe", type="password")
                n_n = st.text_input("Prénom & Nom")
                n_r = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
                if st.button("Créer le compte"):
                    if not valider_mdp(n_p):
                        st.error("Mots de passe trop faible (Majuscule, minuscule, chiffre et caractère spécial requis).")
                    else:
                        sb.table("users").insert({"username": n_u, "password": hash_pwd(n_p), "role": n_r, "nom": n_n}).execute()
                        st.success(f"Compte de {n_n} créé !")
                        st.rerun()
        except:
            st.error("Erreur de chargement des comptes.")

    # --- ONGLET HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("📜 Historique Audit")
        try:
            res = sb.table("logs").select("*").order("id", desc=True).execute()
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        except:
            st.info("Historique vide ou inaccessible.")

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()
