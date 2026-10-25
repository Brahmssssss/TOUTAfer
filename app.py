import streamlit as st
import pandas as pd
import hashlib
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
from datetime import datetime, date
from supabase import create_client
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="TOUTA FER - Sécurisé", page_icon="🏗️", layout="wide")

# --- 2. CONNEXIONS SÉCURISÉES ---
@st.cache_resource
def init_db():
    try:
        # Nettoyage automatique des clés (Anti-erreurs iPhone)
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        
        # Test de disponibilité Supabase
        sb.table("stock").select("count", count="exact").execute()
        
        fb = None
        if "firebase" in st.secrets:
            if not firebase_admin._apps:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            fb = firestore.client()
        return sb, fb, "✅ SYSTÈME OPÉRATIONNEL"
    except Exception as e:
        return None, None, f"❌ ALERTE CONNEXION : {str(e)}"

sb, fb, db_status = init_db()

# --- 3. LOGIQUE DE SÉCURITÉ RENFORCÉE ---
SALT = "TOUTA_FER_DZ_2024_SECURE_TOKEN" # Clé de salage unique

def hash_pwd(password):
    """Hachage sécurisé avec sel (Anti-Brute Force)."""
    salted_pass = password + SALT
    return hashlib.sha256(salted_pass.encode()).hexdigest()

def valider_mdp(password):
    """Vérification stricte (Style Gmail)."""
    if len(password) < 6: return False, "❌ Trop court (6 car. min)."
    if not re.search(r"[A-Z]", password): return False, "❌ MAJUSCULE requise."
    if not re.search(r"[a-z]", password): return False, "❌ minuscule requise."
    if not re.search(r"\d", password): return False, "❌ Chiffre requis."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>/\-_]", password): return False, "❌ Caractère spécial requis."
    return True, ""

def log_action(user_nom, action):
    """Enregistre chaque mouvement avec horodatage précis."""
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data = {"date": now, "utilisateur": str(user_nom), "action": str(action)}
        sb.table("logs").insert(data).execute()
        if fb: fb.collection("logs_backup").add(data)
    except: pass

def envoyer_sauvegarde_mail(user_nom):
    """Envoi sécurisé du bilan Excel."""
    try:
        # Récupération propre des données
        s = pd.DataFrame(sb.table("stock").select("*").execute().data)
        v = pd.DataFrame(sb.table("ventes").select("*").execute().data)
        l = pd.DataFrame(sb.table("logs").select("*").execute().data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            s.to_excel(writer, sheet_name='Stocks', index=False)
            v.to_excel(writer, sheet_name='Ventes_Credits', index=False)
            l.to_excel(writer, sheet_name='Historique', index=False)
        
        msg = MIMEMultipart()
        msg['Subject'] = f"🛡️ TOUTA FER - BACKUP - {datetime.now().strftime('%d/%m/%Y')}"
        msg['From'] = st.secrets["gmail"]["email_envoi"]
        msg['To'] = st.secrets["gmail"]["email_dest"]
        msg.attach(MIMEText(f"Sauvegarde sécurisée demandée par {user_nom}."))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(output.getvalue())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment; filename=TOUTA_FER_SECURE_BACKUP.xlsx")
        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(st.secrets["gmail"]["email_envoi"], st.secrets["gmail"]["mdp_appli"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e: return str(e)

# --- 4. GESTION DE LA SESSION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

# --- 5. ÉCRAN DE CONNEXION ---
if not st.session_state.auth:
    st.markdown(f"<p style='text-align:center; color:grey;'>{db_status}</p>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Identifiez-vous pour accéder à la gestion du fer.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        u_in = st.text_input("Identifiant").strip()
        p_in = st.text_input("Mot de passe", type="password")
        
        if st.button("ACCÉDER AU SYSTÈME", use_container_width=True):
            time.sleep(1) # Ralentit les tentatives de piratage (Anti-Brute Force)
            
            # A. Compte d'urgence
            if u_in == "admin" and p_in == "ToutaAdmin123!":
                st.session_state.auth = True
                st.session_state.user = {"username":"admin", "role":"Développeur", "nom":"Administrateur"}
                log_action("SYSTEM", "Connexion via compte URGENCE")
                st.rerun()
            
            # B. Vérification Supabase
            elif sb:
                try:
                    res = sb.table("users").select("*").eq("username", u_in).eq("password", hash_pwd(p_in)).execute()
                    if res.data:
                        st.session_state.auth = True
                        st.session_state.user = res.data[0]
                        log_action(st.session_state.user['nom'], "Connexion réussie")
                        st.rerun()
                    else:
                        st.error("Identifiant ou mot de passe incorrect.")
                        log_action(u_in, "Tentative de connexion échouée")
                except:
                    st.error("Erreur de communication avec le serveur sécurisé.")
            else:
                st.error("Serveur hors ligne. Contactez le développeur.")

else:
    # --- 6. INTERFACE PRINCIPALE (DÉBLOQUÉE) ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Connecté : **{user['nom']}**")
    st.sidebar.info(f"Rôle : {user['role']}")
    
    # Bouton Sauvegarde par Mail (Patrons seulement)
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        if st.sidebar.button("📧 Envoyer Sauvegarde Mail", use_container_width=True):
            with st.spinner("Cryptage et envoi..."):
                res_m = envoyer_sauvegarde_mail(user['nom'])
                if res_m == True: st.sidebar.success("✅ Mail envoyé avec succès !")
                else: st.sidebar.error(f"❌ Erreur mail : {res_m}")

    menu = ["📦 État des Stocks", "🛒 Nouvelle Vente", "💳 Suivi des Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Gestion Personnel", "📜 Historique Audit"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK (TONNES) ---
    if choice == "📦 État des Stocks":
        st.header("Gestion des Stocks (en Tonnes)")
        try:
            res_s = sb.table("stock").select("*").execute()
            df_s = pd.DataFrame(res_s.data).sort_values('diametre')
            st.dataframe(df_s, use_container_width=True)
            
            if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
                with st.expander("📥 Enregistrer un Arrivage"):
                    d = st.selectbox("Référence Fer", df_s['diametre'].tolist())
                    q = st.number_input("Poids reçu (T)", min_value=0.0, format="%.3f")
                    if st.button("Mettre à jour le stock"):
                        old = df_s.loc[df_s['diametre']==d, 'quantite'].values[0]
                        sb.table("stock").update({"quantite": old + q}).eq("diametre", d).execute()
                        log_action(user['nom'], f"STOCK : Ajout {q}T de {d}")
                        st.success("Données synchronisées !")
                        st.rerun()
        except: st.error("Impossible de lire les stocks.")

    # --- VENTES (CENTIMES + CONTACT) ---
    elif choice == "🛒 Nouvelle Vente":
        st.header("Nouvelle Vente (en Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom du Client").strip()
        tel = col1.text_input("Contact Client (Tél/Email)").strip()
        f = col2.selectbox("Fer à béton", ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","25mm","32mm","40mm"])
        q_v = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = q_v * px
        st.subheader(f"Total à payer : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = str(date.today())
        if is_credit:
            avance = st.number_input("Montant de l'avance (Centimes)", min_value=0.0, max_value=total)
            date_e = str(st.date_input("Date limite pour le reste"))
            st.warning(f"Dette Client : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA TRANSACTION", use_container_width=True):
            if not cl: st.error("Le nom du client est obligatoire.")
            else:
                try:
                    q_act = sb.table("stock").select("quantite").eq("diametre", f).execute().data[0]['quantite']
                    if q_act >= q_v:
                        dv = {"date":str(date.today()), "client":cl, "contact":tel, "fer":f, "qte":q_v, "total":total, "paye":avance, "reste":total-avance, "echeance":date_e, "vendeur":user['nom']}
                        sb.table("ventes").insert(dv).execute()
                        sb.table("stock").update({"quantite": q_act - q_v}).eq("diametre", f).execute()
                        if fb: fb.collection("ventes_backup").add(dv)
                        log_action(user['nom'], f"VENTE : {q_v}T de {f} à {cl} (Reste: {total-avance})")
                        st.success("Vente enregistrée sur les serveurs sécurisés !")
                        st.balloons()
                    else: st.error("Stock insuffisant pour cette vente.")
                except: st.error("Erreur lors de la synchronisation.")

    # --- CRÉDITS ---
    elif choice == "💳 Suivi des Crédits":
        st.header("Clients endettés (Centimes)")
        try:
            res_v = sb.table("ventes").select("*").gt("reste", 0).execute()
            if not res_v.data: st.info("Aucune dette client en cours.")
            else:
                df_c = pd.DataFrame(res_v.data)
                st.dataframe(df_c, use_container_width=True)
                st.divider()
                id_sel = st.selectbox("ID de la vente à encaisser", df_c['id'].tolist())
                mnt = st.number_input("Montant du remboursement (Centimes)", min_value=0.0)
                if st.button("Valider le paiement"):
                    v_sel = df_c[df_c['id'] == id_sel].iloc[0]
                    sb.table("ventes").update({"paye": v_sel['paye'] + mnt, "reste": v_sel['reste'] - mnt}).eq("id", id_sel).execute()
                    log_action(user['nom'], f"CRÉDIT : Reçu {mnt} de {v_sel['client']}")
                    st.success("Crédit mis à jour !")
                    st.rerun()
        except: st.error("Erreur de chargement des crédits.")

    # --- PERSONNEL (HIÉRARCHIE STRICTE) ---
    elif choice == "👥 Gestion Personnel":
        st.header("Sécurité des accès")
        try:
            res_u = sb.table("users").select("username, role, nom").execute()
            df_u = pd.DataFrame(res_u.data)
            st.table(df_u)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("➕ Créer un compte")
                nu = st.text_input("Identifiant").strip()
                np = st.text_input("Mot de passe", type="password")
                nn = st.text_input("Prénom et Nom").strip()
                roles_possibles = ["Commercial", "Comptable", "Gérant", "Patron"]
                if user['role'] in ["Développeur", "Grand Patron"]: roles_possibles.append("Grand Patron")
                nr = st.selectbox("Rôle attribué", roles_possibles)
                
                if st.button("Enregistrer l'accès"):
                    ok, msg = valider_mdp(np)
                    if not ok: st.error(msg)
                    elif nu in df_u['username'].tolist(): st.error("❌ Cet identifiant existe déjà.")
                    else:
                        sb.table("users").insert({"username":nu, "password":hash_pwd(np), "role":nr, "nom":nn}).execute()
                        log_action(user['nom'], f"SÉCURITÉ : Création compte {nu} ({nr})")
                        st.success("Accès créé !")
                        st.rerun()
            
            with col2:
                st.subheader("🗑️ Supprimer un compte")
                if user['role'] == "Développeur": l_s = df_u['username'].tolist()
                elif user['role'] == "Grand Patron": l_s = df_u[df_u['role'] != 'Développeur']['username'].tolist()
                else: l_s = df_u[~df_u['role'].isin(['Développeur','Grand Patron','Patron'])]['username'].tolist()
                
                u_del = st.selectbox("Choisir le compte", [u for u in l_s if u != user['username']])
                if st.button("Supprimer définitivement"):
                    sb.table("users").delete().eq("username", u_del).execute()
                    log_action(user['nom'], f"SÉCURITÉ : Suppression compte {u_del}")
                    st.warning("Accès révoqué.")
                    st.rerun()
        except: st.error("Erreur de gestion des accès.")

    # --- HISTORIQUE ---
    elif choice == "📜 Historique Audit":
        st.header("Historique de Surveillance (Audit)")
        try:
            res_l = sb.table("logs").select("*").order("id", desc=True).execute()
            st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)
        except: st.info("Historique vide.")

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()
