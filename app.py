import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime, date
from supabase import create_client
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- 2. CONNEXION BASES DE DONNÉES ---
@st.cache_resource
def init_db():
    try:
        # Nettoyage des clés
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        
        # Test réel
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
        return None, None, f"❌ Déconnecté : {e}"

sb, fb, db_status = init_db()

# --- 3. FONCTIONS SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
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

# --- 4. CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    if "✅" in db_status: st.success(db_status)
    else: st.error(db_status)

    st.markdown("<h1 style='text-align: center;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        # Compte d'urgence
        if u_in == "admin" and p_in == "ToutaAdmin123!":
            st.session_state.auth = True
            st.session_state.user = {"username": "admin", "role": "Développeur", "nom": "Le Patron"}
            st.rerun()
        elif sb:
            res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
            if res.data:
                st.session_state.auth = True
                st.session_state.user = res.data[0]
                log_action(st.session_state.user['nom'], "S'est connecté")
                st.rerun()
            else: st.error("Identifiant ou mot de passe incorrect.")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"👤 **{user['nom']}** ({user['role']})")
    
    menu = ["📦 Stocks", "🛒 Ventes", "💳 Crédits", "👥 Personnel", "📜 Historique"]
    if user['role'] not in ["Développeur", "Grand Patron", "Patron"]:
        menu = ["📦 Stocks", "🛒 Ventes", "💳 Crédits"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK ---
    if choice == "📦 Stocks":
        st.header("Gestion des Stocks (Tonnes)")
        res = sb.table("stock").select("*").execute()
        df_s = pd.DataFrame(res.data)
        st.dataframe(df_s, use_container_width=True)
        
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter du Fer"):
                d = st.selectbox("Référence", df_s['diametre'].tolist())
                q = st.number_input("Tonnes", min_value=0.0, format="%.3f")
                if st.button("Valider l'ajout"):
                    old_q = df_s.loc[df_s['diametre']==d, 'quantite'].values[0]
                    sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                    log_action(user['nom'], f"Ajout {q}T de {d}")
                    st.success("Stock mis à jour")
                    st.rerun()

    # --- VENTES ---
    elif choice == "🛒 Ventes":
        st.header("Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom Client")
        f = col2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q = col2.number_input("Quantité (T)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        total = q * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Échéance"))
        
        if st.button("🚀 VALIDER LA VENTE"):
            if not cl: st.error("Nom client manquant")
            else:
                q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                if q_act >= q:
                    data_v = {"date": str(date.today()), "client": cl, "fer": f, "qte": q, "total": total, "paye": avance, "reste": total-avance, "echeance": date_e, "vendeur": user['nom']}
                    sb.table("ventes").insert(data_v).execute()
                    sb.table("stock").update({"quantite": q_act - q}).eq("diametre", f).execute()
                    if fb: fb.collection("ventes_backup").add(data_v)
                    log_action(user['nom'], f"Vente {q}T de {f} à {cl}")
                    st.success("Vente enregistrée !")
                    st.balloons()
                else: st.error("Stock insuffisant")

    # --- CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Crédits")
        res_v = sb.table("ventes").select("*").gt("reste", 0).execute()
        if not res_v.data:
            st.info("Aucun crédit en cours.")
        else:
            df_c = pd.DataFrame(res_v.data)
            st.dataframe(df_c, use_container_width=True)
            st.divider()
            id_sel = st.selectbox("ID de la vente à rembourser", df_c['id'].tolist())
            mnt = st.number_input("Montant reçu (Centimes)", min_value=0.0)
            if st.button("Valider remboursement"):
                v_data = df_c[df_c['id'] == id_sel].iloc[0]
                sb.table("ventes").update({"paye": v_data['paye'] + mnt, "reste": v_data['reste'] - mnt}).eq("id", id_sel).execute()
                log_action(user['nom'], f"Remboursement {mnt} pour vente {id_sel}")
                st.rerun()

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion des Comptes")
        res_u = sb.table("users").select("username, role, nom").execute()
        df_u = pd.DataFrame(res_u.data)
        st.table(df_u)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Nouveau")
            nu = st.text_input("Identifiant")
            np = st.text_input("Mot de passe", type="password")
            nn = st.text_input("Nom")
            nr = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
            if st.button("Créer"):
                if valider_mdp(np):
                    sb.table("users").insert({"username": nu, "password": hash_pwd(np), "role": nr, "nom": nn}).execute()
                    log_action(user['nom'], f"Créé compte {nu}")
                    st.rerun()
                else: st.error("Mot de passe trop simple (Maj, min, chiffre, spécial requis)")
        
        with col2:
            st.subheader("🗑️ Supprimer")
            if user['role'] == "Développeur": l_suppr = [u for u in df_u['username'].tolist() if u != user['username']]
            elif user['role'] == "Grand Patron": l_suppr = [r['username'] for i,r in df_u.iterrows() if r['role'] != 'Développeur' and r['username'] != user['username']]
            else: l_suppr = [r['username'] for i,r in df_u.iterrows() if r['role'] not in ['Développeur', 'Grand Patron', 'Patron']]
            
            u_del = st.selectbox("Supprimer quel compte ?", l_suppr) if l_suppr else None
            if u_del and st.button("Supprimer Définitivement"):
                sb.table("users").delete().eq("username", u_del).execute()
                log_action(user['nom'], f"Supprimé compte {u_del}")
                st.rerun()

    # --- HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("Journal d'Audit")
        res_l = sb.table("logs").select("*").order("id", desc=True).execute()
        st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
