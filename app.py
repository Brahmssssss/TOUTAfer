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

# --- 2. CONNEXION AUX SERVEURS ---
@st.cache_resource
def init_db():
    try:
        # Nettoyage automatique des clés
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        
        # Test de lecture
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

# --- 3. FONCTIONS SÉCURITÉ & MDP ---
def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valider_mdp(password):
    """Vérifie les règles Gmail avec TOUS les caractères spéciaux (./-_ etc)"""
    if len(password) < 6: return False, "❌ Le mot de passe doit faire au moins 6 caractères."
    if not re.search(r"[A-Z]", password): return False, "❌ Il faut au moins une MAJUSCULE."
    if not re.search(r"[a-z]", password): return False, "❌ Il faut au moins une minuscule."
    if not re.search(r"\d", password): return False, "❌ Il faut au moins un chiffre."
    # Cette ligne autorise maintenant ./!@#$%^&*() et tous les autres
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>/\-_]", password): 
        return False, "❌ Il faut au moins un caractère spécial (ex: . / @ ! -)."
    return True, ""

def log_action(user_nom, action):
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        data = {"date": now, "utilisateur": user_nom, "action": action}
        sb.table("logs").insert(data).execute()
        if fb: fb.collection("logs_backup").add(data)
    except: pass

# --- 4. INTERFACE DE CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    if "✅" in db_status: st.success(db_status)
    else: st.error(db_status)

    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    u_in = st.text_input("Identifiant")
    p_in = st.text_input("Mot de passe", type="password")
    
    if st.button("SE CONNECTER", use_container_width=True):
        # COMPTE D'URGENCE
        if u_in == "admin" and p_in == "ToutaAdmin123!":
            st.session_state.auth = True
            st.session_state.user = {"username":"admin", "role":"Développeur", "nom":"Le Patron"}
            st.rerun()
        elif sb:
            try:
                res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
                if res.data:
                    st.session_state.auth = True
                    st.session_state.user = res.data[0]
                    log_action(st.session_state.user['nom'], "S'est connecté")
                    st.rerun()
                else: st.error("Identifiant ou mot de passe incorrect.")
            except: st.error("Erreur de communication avec la base de données.")
else:
    # --- 5. INTERFACE PRINCIPALE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"👤 **{user['nom']}**")
    st.sidebar.write(f"Rôle : `{user['role']}`")
    
    # Menu selon les rôles
    menu = ["📦 Stocks", "🛒 Ventes", "💳 Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    
    choice = st.sidebar.radio("Menu de gestion", menu)

    # --- STOCK (TONNES) ---
    if choice == "📦 Stocks":
        st.header("Gestion des Stocks de Fer (Tonnes)")
        try:
            res = sb.table("stock").select("*").execute()
            df_s = pd.DataFrame(res.data).sort_values('diametre')
            st.dataframe(df_s, use_container_width=True)
            
            if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
                with st.expander("📥 Ajouter du Fer au stock"):
                    d = st.selectbox("Choisir le diamètre", df_s['diametre'].tolist())
                    q = st.number_input("Nombre de tonnes reçues", min_value=0.0, format="%.3f")
                    if st.button("Confirmer l'ajout"):
                        old_q = df_s.loc[df_s['diametre']==d, 'quantite'].values[0]
                        sb.table("stock").update({"quantite": old_q + q}).eq("diametre", d).execute()
                        log_action(user['nom'], f"A ajouté {q}T de fer {d}")
                        st.success("Stock mis à jour !")
                        st.rerun()
        except: st.error("Impossible de charger les données du stock.")

    # --- VENTES (CENTIMES) ---
    elif choice == "🛒 Ventes":
        st.header("Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom du Client")
        tel = col1.text_input("Téléphone")
        f = col2.selectbox("Fer à béton", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q_v = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix par Tonne (Centimes)", min_value=0.0)
        
        total = q_v * px
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Date prévue du reste"))
            st.warning(f"Reste à payer : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE DÉFINITIVEMENT", use_container_width=True):
            if not cl: st.error("Le nom du client est obligatoire.")
            else:
                try:
                    q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                    if q_act >= q_v:
                        data_v = {"date": str(date.today()), "client": cl, "contact": tel, "fer": f, "qte": q_v, "total": total, "paye": avance, "reste": total-avance, "echeance": date_e, "vendeur": user['nom']}
                        sb.table("ventes").insert(data_v).execute()
                        sb.table("stock").update({"quantite": q_act - q_v}).eq("diametre", f).execute()
                        if fb: fb.collection("ventes_backup").add(data_v)
                        log_action(user['nom'], f"Vente {q_v}T de {f} à {cl}")
                        st.success("Vente réussie chez TOUTA FER !")
                        st.balloons()
                    else: st.error("Stock insuffisant !")
                except: st.error("Erreur lors de l'enregistrement.")

    # --- CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Crédits Clients")
        res_v = sb.table("ventes").select("*").gt("reste", 0).execute()
        if not res_v.data: st.info("Aucun crédit en cours.")
        else:
            df_c = pd.DataFrame(res_v.data)
            st.dataframe(df_c, use_container_width=True)
            st.divider()
            id_sel = st.selectbox("ID de la vente à rembourser", df_c['id'].tolist())
            mnt = st.number_input("Montant remboursé (Centimes)", min_value=0.0)
            if st.button("Valider le paiement"):
                v_sel = df_c[df_c['id'] == id_sel].iloc[0]
                sb.table("ventes").update({"paye": v_sel['paye'] + mnt, "reste": v_sel['reste'] - mnt}).eq("id", id_sel).execute()
                log_action(user['nom'], f"Paiement crédit {mnt} de {v_sel['client']}")
                st.rerun()

    # --- PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("Gestion du Personnel")
        res_u = sb.table("users").select("*").execute()
        df_u = pd.DataFrame(res_u.data)
        st.table(df_u[['username', 'role', 'nom']])
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Ajouter un employé")
            nu, np, nn = st.text_input("Identifiant"), st.text_input("Passe", type="password"), st.text_input("Nom complet")
            nr = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant", "Patron", "Grand Patron"])
            if st.button("Créer le compte"):
                ok, msg = valider_mdp(np)
                if not ok: st.error(msg)
                else:
                    sb.table("users").insert({"username": nu, "password": hash_pwd(np), "role": nr, "nom": nn}).execute()
                    log_action(user['nom'], f"A créé le compte {nu}")
                    st.success("Compte créé !")
                    st.rerun()
        
        with col2:
            st.subheader("🗑️ Supprimer un compte")
            if user['role'] == "Développeur": l_suppr = df_u['username'].tolist()
            elif user['role'] == "Grand Patron": l_suppr = df_u[df_u['role'] != 'Développeur']['username'].tolist()
            else: l_suppr = df_u[~df_u['role'].isin(['Développeur','Grand Patron','Patron'])]['username'].tolist()
            u_del = st.selectbox("Compte à supprimer", [u for u in l_suppr if u != user['username']])
            if u_del and st.button("Supprimer Définitivement"):
                sb.table("users").delete().eq("username", u_del).execute()
                log_action(user['nom'], f"A supprimé le compte {u_del}")
                st.rerun()

    # --- HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("Journal d'Audit TOUTA FER")
        res_l = sb.table("logs").select("*").order("id", desc=True).execute()
        st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()
