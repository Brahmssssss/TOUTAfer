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

# --- 2. CONNEXION ---
@st.cache_resource
def init_db():
    try:
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        sb.table("stock").select("count", count="exact").execute()
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

# --- 3. SÉCURITÉ ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    if len(password) < 6: return False, "❌ 6 caractères minimum."
    if not re.search(r"[A-Z]", password): return False, "❌ Il faut une MAJUSCULE."
    if not re.search(r"[a-z]", password): return False, "❌ Il faut une minuscule."
    if not re.search(r"\d", password): return False, "❌ Il faut un chiffre."
    if not re.search(r"[!@#$%^&*()]", password): return False, "❌ Il faut un symbole."
    return True, ""

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
                log_action(st.session_state.user['nom'], "S'est connecté")
                st.rerun()
            else: st.error("Identifiant ou mot de passe incorrect.")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"👤 {user['nom']}")
    
    menu = ["📦 Stocks", "🛒 Ventes", "💳 Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK ---
    if choice == "📦 Stocks":
        st.header("Gestion des Stocks (Tonnes)")
        res = sb.table("stock").select("*").execute()
        df_s = pd.DataFrame(res.data).sort_values('diametre')
        st.dataframe(df_s, use_container_width=True)
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter du Fer"):
                d = st.selectbox("Référence", df_s['diametre'].tolist())
                q = st.number_input("Tonnes", min_value=0.0, format="%.3f")
                if st.button("Confirmer l'ajout"):
                    old_q = df_s.loc[df_s['diametre']==d, 'quantite'].values[0]
                    sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                    log_action(user['nom'], f"Stock : +{q}T de {d}")
                    st.success("Mis à jour !")
                    st.rerun()

    # --- VENTES ---
    elif choice == "🛒 Ventes":
        st.header("Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom Client")
        tel = col1.text_input("Téléphone")
        f = col2.selectbox("Fer", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","22mm","25mm","32mm","40mm"])
        q = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
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
            if not cl: st.error("Client manquant")
            else:
                q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                if q_act >= q:
                    data_v = {"date": str(date.today()), "client": cl, "contact": tel, "fer": f, "qte": q, "total": total, "paye": avance, "reste": total-avance, "echeance": date_e, "vendeur": user['nom']}
                    sb.table("ventes").insert(data_v).execute()
                    sb.table("stock").update({"quantite": q_act - q}).eq("diametre", f).execute()
                    if fb: fb.collection("ventes_backup").add(data_v)
                    log_action(user['nom'], f"Vente {q}T de {f} à {cl}")
                    st.success("Vente réussie !")
                    st.balloons()
                else: st.error("Stock insuffisant")

    # --- CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Dettes")
        res_v = sb.table("ventes").select("*").gt("reste", 0).execute()
        if not res_v.data: st.info("Aucun crédit.")
        else:
            df_c = pd.DataFrame(res_v.data)
            st.dataframe(df_c, use_container_width=True)
            id_sel = st.selectbox("ID Vente", df_c['id'].tolist())
            mnt = st.number_input("Montant Remboursé (Centimes)", min_value=0.0)
            if st.button("Encaisser"):
                v_data = df_c[df_c['id'] == id_sel].iloc[0]
                sb.table("ventes").update({"paye": v_data['paye'] + mnt, "reste": v_data['reste'] - mnt}).eq("id", id_sel).execute()
                log_action(user['nom'], f"Encaissement {mnt} de {v_data['client']}")
                st.rerun()

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion Personnel")
        res_u = sb.table("users").select("*").execute()
        df_u = pd.DataFrame(res_u.data)
        st.table(df_u[['username', 'role', 'nom']])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Ajouter")
            nu, np, nn = st.text_input("Identifiant"), st.text_input("Passe", type="password"), st.text_input("Nom")
            nr = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
            if st.button("Créer"):
                ok, msg = valider_mdp(np)
                if not ok: st.error(msg)
                else:
                    sb.table("users").insert({"username": nu, "password": hash_pwd(np), "role": nr, "nom": nn}).execute()
                    log_action(user['nom'], f"A créé le compte {nu}")
                    st.rerun()
        with col2:
            st.subheader("🗑️ Supprimer")
            if user['role'] == "Développeur": l_s = df_u['username'].tolist()
            elif user['role'] == "Grand Patron": l_s = df_u[df_u['role'] != 'Développeur']['username'].tolist()
            else: l_s = df_u[~df_u['role'].isin(['Développeur','Grand Patron','Patron'])]['username'].tolist()
            u_del = st.selectbox("Compte", [u for u in l_s if u != user['username']])
            if st.button("Supprimer"):
                sb.table("users").delete().eq("username", u_del).execute()
                log_action(user['nom'], f"A supprimé {u_del}")
                st.rerun()

    # --- HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("Journal d'Audit")
        res_l = sb.table("logs").select("*").order("id", desc=True).execute()
        st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
