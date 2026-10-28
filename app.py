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
        s_url = st.secrets["supabase"]["url"].strip().rstrip('/')
        s_key = st.secrets["supabase"]["key"].strip()
        sb = create_client(s_url, s_key)
        
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

# --- 3. LOGIQUE DE SÉCURITÉ & OUTILS ---
SALT = "TOUTA_FER_DZ_2024_SECURE_TOKEN"
DIAMETRES_STANDARDS = ["6mm","8mm","10mm","12mm","14mm","16mm","18mm","20mm","22mm","25mm","32mm","40mm"]

def hash_pwd(password):
    salted_pass = password + SALT
    return hashlib.sha256(salted_pass.encode()).hexdigest()

def valider_mdp(password):
    if len(password) < 6: return False, "❌ Trop court (6 car. min)."
    if not re.search(r"[A-Z]", password): return False, "❌ MAJUSCULE requise."
    if not re.search(r"[a-z]", password): return False, "❌ minuscule requise."
    if not re.search(r"\d", password): return False, "❌ Chiffre requis."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>/\-_]", password): return False, "❌ Caractère spécial requis."
    return True, ""

def log_action(user_nom, action):
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data = {"date": now, "utilisateur": str(user_nom), "action": str(action)}
        sb.table("logs").insert(data).execute()
        if fb: fb.collection("logs_backup").add(data)
    except: pass

def extraire_tableau_receptions(logs_data):
    """Transforme l'historique des réceptions en un tableau détaillé avec les prix."""
    receptions = []
    for row in logs_data:
        act = str(row.get("action", ""))
        if act.startswith("RÉCEPTION |"):
            parts = [p.strip() for p in act.split("|")]
            if len(parts) >= 7:
                receptions.append({
                    "Date": row.get("date"),
                    "Fournisseur / Usine": parts[1],
                    "N° BL / Camion": parts[2],
                    "Diamètre": parts[3],
                    "Quantité (T)": float(parts[4]),
                    "Prix d'Achat / T (Centimes)": parts[5],
                    "Coût Total (Centimes)": parts[6],
                    "Réceptionné par": row.get("utilisateur")
                })
    return pd.DataFrame(receptions)

def envoyer_sauvegarde_mail(user_nom):
    try:
        s = pd.DataFrame(sb.table("stock").select("*").execute().data)
        v = pd.DataFrame(sb.table("ventes").select("*").execute().data)
        l_raw = sb.table("logs").select("*").order("id", desc=True).execute().data
        l = pd.DataFrame(l_raw)
        df_rec = extraire_tableau_receptions(l_raw)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            s.to_excel(writer, sheet_name='Stocks', index=False)
            df_rec.to_excel(writer, sheet_name='Achats_Receptions', index=False)
            v.to_excel(writer, sheet_name='Ventes_Credits', index=False)
            l.to_excel(writer, sheet_name='Historique_Audit', index=False)
        
        msg = MIMEMultipart()
        msg['Subject'] = f"🛡️ TOUTA FER - BACKUP - {datetime.now().strftime('%d/%m/%Y')}"
        msg['From'] = st.secrets["gmail"]["email_envoi"]
        msg['To'] = st.secrets["gmail"]["email_dest"]
        msg.attach(MIMEText(f"Sauvegarde complète (Stocks, Achats/Réceptions, Ventes, Crédits) demandée par {user_nom}."))

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
            time.sleep(1)
            if u_in == "admin" and p_in == "ToutaAdmin123!":
                st.session_state.auth = True
                st.session_state.user = {"username":"admin", "role":"Développeur", "nom":"Administrateur"}
                log_action("SYSTEM", "Connexion via compte URGENCE")
                st.rerun()
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
    # --- 6. INTERFACE PRINCIPALE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Connecté : **{user['nom']}**")
    st.sidebar.info(f"Rôle : {user['role']}")
    
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        if st.sidebar.button("📧 Envoyer Sauvegarde Mail", use_container_width=True):
            with st.spinner("Cryptage et envoi..."):
                res_m = envoyer_sauvegarde_mail(user['nom'])
                if res_m == True: st.sidebar.success("✅ Mail envoyé avec succès !")
                else: st.sidebar.error(f"❌ Erreur mail : {res_m}")

    # Définition du menu selon les rôles
    menu = ["📦 État des Stocks", "🛒 Nouvelle Vente", "💳 Suivi des Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
        menu.insert(1, "🚚 Réception Fer")
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Gestion Personnel", "📜 Historique Audit"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK (TONNES) ---
    if choice == "📦 État des Stocks":
        st.header("📦 État des Stocks (en Tonnes)")
        try:
            res_s = sb.table("stock").select("*").execute()
            df_s = pd.DataFrame(res_s.data)
            if not df_s.empty:
                st.dataframe(df_s.sort_values('diametre'), use_container_width=True)
            else:
                st.info("Aucun stock initialisé.")
        except: st.error("Impossible de lire les stocks.")

    # --- ONGLET : RÉCEPTION DE FER (AVEC PRIX D'ACHAT DÉTAILLÉ) ---
    elif choice == "🚚 Réception Fer":
        st.header("🚚 Réception de Fer & Suivi des Prix d'Achat")
        try:
            res_s = sb.table("stock").select("*").execute()
            df_s = pd.DataFrame(res_s.data)
            
            col1, col2 = st.columns(2)
            fournisseur = col1.text_input("Usine / Fournisseur (ex: Tosyali, Bellara)").strip().replace("|", "-")
            bon_livraison = col1.text_input("N° Bon de Livraison / Camion").strip().replace("|", "-")
            diam_recu = col2.selectbox("Diamètre du Fer reçu", DIAMETRES_STANDARDS)
            qte_recue = col2.number_input("Quantité reçue (en Tonnes)", min_value=0.001, format="%.3f")
            
            prix_achat = st.number_input("Prix d'Achat par Tonne (en Centimes)", min_value=0.0, step=1000.0)
            total_achat = qte_recue * prix_achat
            
            st.subheader(f"💰 Coût Total de l'arrivage : {total_achat:,.0f} Centimes")
            
            if st.button("📥 VALIDER LA RÉCEPTION ET LE PRIX D'ACHAT", use_container_width=True):
                if not fournisseur:
                    st.error("Veuillez indiquer le nom du fournisseur ou de l'usine.")
                elif prix_achat <= 0:
                    st.error("Veuillez indiquer le prix d'achat pour suivre vos coûts.")
                else:
                    # Vérifie si le diamètre existe déjà dans la table stock
                    if not df_s.empty and diam_recu in df_s['diametre'].values:
                        old_q = float(df_s.loc[df_s['diametre']==diam_recu, 'quantite'].values[0])
                        new_q = old_q + qte_recue
                        sb.table("stock").update({"quantite": new_q}).eq("diametre", diam_recu).execute()
                    else:
                        new_q = qte_recue
                        sb.table("stock").insert({"diametre": diam_recu, "quantite": new_q}).execute()
                    
                    # Formatage structuré pour reconstruire le tableau détaillé des prix
                    details_rec = f"RÉCEPTION | {fournisseur} | {bon_livraison} | {diam_recu} | {qte_recue:.3f} | {prix_achat:,.0f} | {total_achat:,.0f}"
                    log_action(user['nom'], details_rec)
                    
                    if fb:
                        fb.collection("receptions_backup").add({
                            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "fournisseur": fournisseur, "bon": bon_livraison,
                            "fer": diam_recu, "tonnes": qte_recue,
                            "prix_unitaire_centimes": prix_achat, "cout_total_centimes": total_achat,
                            "par": user['nom']
                        })
                    st.success(f"✅ Réception enregistrée ! Stock de {diam_recu} : {new_q:.3f} T (Acheté à {prix_achat:,.0f} Centimes/T).")
                    st.balloons()
            
            st.divider()
            st.subheader("📊 Historique détaillé des Achats et Fluctuation des Prix")
            
            res_l = sb.table("logs").select("*").order("id", desc=True).execute()
            df_receptions = extraire_tableau_receptions(res_l.data if res_l.data else [])
            
            if not df_receptions.empty:
                # Filtre pour comparer l'évolution du prix d'un fer précis (ex: 12mm hier vs aujourd'hui)
                filtre_diam = st.selectbox("🔍 Filtrer par diamètre pour comparer les prix d'achat :", ["Tous les diamètres"] + DIAMETRES_STANDARDS)
                if filtre_diam != "Tous les diamètres":
                    df_receptions = df_receptions[df_receptions["Diamètre"] == filtre_diam]
                
                st.dataframe(df_receptions, use_container_width=True)
            else:
                st.info("Aucune réception détaillée enregistrée pour le moment.")
        except Exception as e:
            st.error(f"Erreur lors de l'accès aux réceptions : {e}")

    # --- VENTES (CENTIMES + CONTACT) ---
    elif choice == "🛒 Nouvelle Vente":
        st.header("🛒 Nouvelle Vente (en Centimes)")
        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom du Client").strip()
        tel = col1.text_input("Contact Client (Tél/Email)").strip()
        f = col2.selectbox("Fer à béton", DIAMETRES_STANDARDS)
        q_v = col2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix de Vente / Tonne (Centimes)", min_value=0.0)
        
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
                    res_st = sb.table("stock").select("quantite").eq("diametre", f).execute()
                    q_act = float(res_st.data[0]['quantite']) if res_st.data else 0.0
                    if q_act >= q_v:
                        dv = {"date":str(date.today()), "client":cl, "contact":tel, "fer":f, "qte":q_v, "total":total, "paye":avance, "reste":total-avance, "echeance":date_e, "vendeur":user['nom']}
                        sb.table("ventes").insert(dv).execute()
                        sb.table("stock").update({"quantite": q_act - q_v}).eq("diametre", f).execute()
                        if fb: fb.collection("ventes_backup").add(dv)
                        log_action(user['nom'], f"VENTE : {q_v}T de {f} à {cl} (Prix/T: {px:,.0f} | Reste: {total-avance:,.0f})")
                        st.success("Vente enregistrée sur les serveurs sécurisés !")
                        st.balloons()
                    else: st.error(f"Stock insuffisant ({q_act:.3f} T disponible).")
                except: st.error("Erreur lors de la synchronisation.")

    # --- CRÉDITS ---
    elif choice == "💳 Suivi des Crédits":
        st.header("💳 Clients endettés (Centimes)")
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
                    log_action(user['nom'], f"CRÉDIT : Reçu {mnt:,.0f} de {v_sel['client']}")
                    st.success("Crédit mis à jour !")
                    st.rerun()
        except: st.error("Erreur de chargement des crédits.")

    # --- PERSONNEL ---
    elif choice == "👥 Gestion Personnel":
        st.header("👥 Sécurité des accès")
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
                    elif not df_u.empty and nu in df_u['username'].tolist(): st.error("❌ Cet identifiant existe déjà.")
                    else:
                        sb.table("users").insert({"username":nu, "password":hash_pwd(np), "role":nr, "nom":nn}).execute()
                        log_action(user['nom'], f"SÉCURITÉ : Création compte {nu} ({nr})")
                        st.success("Accès créé !")
                        st.rerun()
            
            with col2:
                st.subheader("🗑️ Supprimer un compte")
                if not df_u.empty:
                    if user['role'] == "Développeur": l_s = df_u['username'].tolist()
                    elif user['role'] == "Grand Patron": l_s = df_u[df_u['role'] != 'Développeur']['username'].tolist()
                    else: l_s = df_u[~df_u['role'].isin(['Développeur','Grand Patron','Patron'])]['username'].tolist()
                    
                    u_del = st.selectbox("Choisir le compte", [u for u in l_s if u != user['username']])
                    if u_del and st.button("Supprimer définitivement"):
                        sb.table("users").delete().eq("username", u_del).execute()
                        log_action(user['nom'], f"SÉCURITÉ : Suppression compte {u_del}")
                        st.warning("Accès révoqué.")
                        st.rerun()
        except: st.error("Erreur de gestion des accès.")

    # --- HISTORIQUE ---
    elif choice == "📜 Historique Audit":
        st.header("📜 Historique de Surveillance (Audit)")
        try:
            res_l = sb.table("logs").select("*").order("id", desc=True).execute()
            st.dataframe(pd.DataFrame(res_l.data), use_container_width=True)
        except: st.info("Historique vide.")

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()