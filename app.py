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
st.set_page_config(page_title="TOUTA FER - Gestion", page_icon="🏗️", layout="wide")

# --- 2. CATALOGUE OFFICIEL EXTRAIT DE TA FEUILLE PDF (37 ARTICLES) ---
STOCK_INITIAL_PDF = [
    ("T.166", "FIL BOTLAGE", "KG", 1276.000, 0.000, 0.000, 1276.000),
    ("T.164", "FIL D'ATTACHE 10KG", "KG", 1147.000, 0.000, 0.000, 1147.000),
    ("T.162", "FIL MACHINE 06 M/M TRF", "T", 37.500, 0.000, 0.000, 37.500),
    ("TS.133", "FIL MACHINE 06 M/M TRF 1006", "T", 89.000, 0.000, 0.000, 89.000),
    ("TS.158", "FIL MACHINE 08 M/M TRF", "T", 9.000, 0.000, 0.000, 9.000),
    ("B.10", "FIL MACHINE 09 M/M", "T", 24.000, 0.000, 0.000, 24.000),
    ("B.14", "FIL MACHINE 09 M/M production", "T", 3.000, 0.000, 0.000, 3.000),
    ("B.11", "FIL MACHINE 10 M/M TRF", "T", 10.000, 0.000, 0.000, 10.000),
    ("T.163", "FIL MACHINE5.5 M/M", "T", 7.000, 0.000, 0.000, 7.000),
    ("TS.76", "FIL MACHINE5.5 M/M TRS", "T", 2.000, 0.000, 0.000, 2.000),
    ("B.9", "M.CHEVRON 4M", "P", 0.000, 0.000, 0.000, 0.000),
    ("TS.248", "M.DEMI MADRI 4*(40*90) HJ", "P", 2.000, 0.000, 0.000, 2.000),
    ("TS.229", "MADRI 18*40 3.5 M", "P", 5.000, 0.000, 0.000, 5.000),
    ("B.7", "MADRI 3M 20", "P", 8.000, 0.000, 0.000, 8.000),
    ("TS.250", "MADRI 4*(40*135) HJ", "P", 3.000, 0.000, 0.000, 3.000),
    ("B.8", "MADRI 4M 18*40", "P", 18.000, 0.000, 0.000, 18.000),
    ("TS.246", "MADRI 4M 18*40 HJ", "P", 15.000, 0.000, 0.000, 15.000),
    ("TS.240", "MULTIPILIER 18 ARSER-PLEX", "P", 6.000, 0.000, 0.000, 6.000),
    ("TS.136", "MULTIPLIER 15 ARSER-PLEX", "P", 21.000, 0.000, 0.000, 21.000),
    ("TS.238", "MULTIPLIER 18 FORM", "P", 26.000, 0.000, 0.000, 26.000),
    ("TS.247", "PLANCHE 4(21*115) HJ", "P", 6.000, 0.000, 0.000, 6.000),
    ("TS.249", "PLANCHE 4*(21*180) HJ", "P", 4.000, 0.000, 0.000, 4.000),
    ("TS.84", "POINT 08", "P", 52.000, 0.000, 0.000, 52.000),
    ("TS.21", "POINTE 05", "P", 397.000, 0.000, 0.000, 397.000),
    ("T.167", "POINTE 06", "P", 382.000, 0.000, 0.000, 382.000),
    ("T.168", "POINTE 07", "P", 196.000, 0.000, 0.000, 196.000),
    ("T.169", "POINTE 10", "P", 169.000, 0.000, 0.000, 169.000),
    ("T.155", "ROND A BETON D08 M/M T", "T", 157.000, 0.000, 2.000, 155.000),
    ("T.156", "ROND A BETON D10 M/M T", "T", 3.000, 0.000, 0.000, 3.000),
    ("T.157", "ROND A BETON D12 M/M T", "T", 85.000, 0.000, 5.000, 80.000),
    ("T.158", "ROND A BETON D14 M/M T", "T", 1.000, 0.000, 0.000, 1.000),
    ("T.159", "ROND A BETON D16 M/M T", "T", 108.000, 0.000, 4.000, 104.000),
    ("T.160", "ROND A BETON D20 M/M T", "T", 133.000, 0.000, 0.000, 133.000),
    ("T.161", "ROND A BETON D25 M/M T", "T", 183.000, 0.000, 0.000, 183.000),
    ("T.203", "ROND A BETON D32 M/M T", "T", 92.000, 0.000, 0.000, 92.000),
    ("TS.261", "TREILLIS SOUDES LONG 40M*02M D4", "RLX", 47.000, 93.000, 0.000, 140.000),
    ("TS.263", "TRIELLE A SOUDE D3.3MM 15*17CM 2*40M", "RLX", 152.000, 0.000, 0.000, 152.000)
]

DICT_PDF = {f"{ref} | {des} | {um}": (init_v, ent_v, sort_v, fin_v) for ref, des, um, init_v, ent_v, sort_v, fin_v in STOCK_INITIAL_PDF}

# --- 3. CONNEXIONS SÉCURISÉES ---
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

def synchroniser_stock_pdf(forcer=False):
    if not sb: return
    try:
        res = sb.table("stock").select("*").execute()
        existants = [r['diametre'] for r in res.data] if res.data else []
        
        if forcer or not any("T.155 | ROND A BETON" in x for x in existants):
            for old in ['6mm','8mm','10mm','12mm','14mm','16mm','18mm','20mm','22mm','25mm','32mm','40mm']:
                if old in existants:
                    sb.table("stock").delete().eq("diametre", old).execute()
            
            for ref, des, um, init_v, ent_v, sort_v, fin_v in STOCK_INITIAL_PDF:
                cle_article = f"{ref} | {des} | {um}"
                if forcer or cle_article not in existants:
                    sb.table("stock").upsert({"diametre": cle_article, "quantite": fin_v}).execute()
    except Exception:
        pass

synchroniser_stock_pdf(forcer=False)

def formater_dataframe_stock(raw_data):
    ordres_ref = [x[0] for x in STOCK_INITIAL_PDF]
    lignes = []
    for r in raw_data:
        cle = str(r.get('diametre', ''))
        qte_finale = float(r.get('quantite', 0.0))
        if "|" in cle:
            parts = [p.strip() for p in cle.split("|")]
            ref = parts[0] if len(parts) > 0 else ""
            des = parts[1] if len(parts) > 1 else cle
            um = parts[2] if len(parts) > 2 else "T"
        else:
            ref, des, um = "-", cle, "T"
            
        init_v, ent_pdf, sort_pdf, fin_pdf = DICT_PDF.get(cle, (qte_finale, 0.0, 0.0, qte_finale))
        diff = qte_finale - fin_pdf
        ent_tot = ent_pdf + (diff if diff > 0 else 0.0)
        sort_tot = sort_pdf + (abs(diff) if diff < 0 else 0.0)
        rang = ordres_ref.index(ref) if ref in ordres_ref else 999
        
        lignes.append({
            "Rang": rang,
            "Clé_Interne": cle,
            "Référence": ref,
            "Désignation": des,
            "UM": um,
            "FDX Initial": init_v,
            "FDX Entrée": ent_tot,
            "FDX Sortie": sort_tot,
            "FDX Final": qte_finale
        })
    df_res = pd.DataFrame(lignes)
    if not df_res.empty:
        df_res = df_res.sort_values("Rang").drop(columns=["Rang"])
    return df_res

# --- 4. LOGIQUE DE SÉCURITÉ & EXTRACTION ---
SALT = "TOUTA_FER_DZ_2024_SECURE_TOKEN"

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
                    "Article": parts[3],
                    "Quantité": float(parts[4]),
                    "Prix d'Achat Unitaire (Centimes)": parts[5],
                    "Coût Total (Centimes)": parts[6],
                    "Réceptionné par": row.get("utilisateur")
                })
    return pd.DataFrame(receptions)

def extraire_tableau_caisse(logs_data):
    """Extrait tous les mouvements manuels de la Caisse (Entrées et Dépenses)."""
    mouvements = []
    for row in logs_data:
        act = str(row.get("action", ""))
        if act.startswith("CAISSE |"):
            parts = [p.strip() for p in act.split("|")]
            if len(parts) >= 6:
                try:
                    montant_val = float(parts[4].replace(",", "").replace(" ", ""))
                except:
                    montant_val = 0.0
                mouvements.append({
                    "Date": row.get("date"),
                    "Sens": parts[1],
                    "Catégorie": parts[2],
                    "Mode": parts[3],
                    "Montant_Num": montant_val,
                    "Montant (Centimes)": f"{montant_val:,.0f}",
                    "Motif / Bénéficiaire": parts[5],
                    "Opérateur": row.get("utilisateur")
                })
    return pd.DataFrame(mouvements)

def envoyer_sauvegarde_mail(user_nom):
    try:
        raw_s = sb.table("stock").select("*").execute().data
        s = formater_dataframe_stock(raw_s).drop(columns=["Clé_Interne"], errors="ignore")
        v = pd.DataFrame(sb.table("ventes").select("*").execute().data)
        l_raw = sb.table("logs").select("*").order("id", desc=True).execute().data
        l = pd.DataFrame(l_raw)
        df_rec = extraire_tableau_receptions(l_raw)
        df_cai = extraire_tableau_caisse(l_raw).drop(columns=["Montant_Num"], errors="ignore")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            s.to_excel(writer, sheet_name='Etat_du_Stock', index=False)
            df_rec.to_excel(writer, sheet_name='Achats_Receptions', index=False)
            v.to_excel(writer, sheet_name='Ventes_Credits', index=False)
            df_cai.to_excel(writer, sheet_name='Journal_Caisse', index=False)
            l.to_excel(writer, sheet_name='Historique_Audit', index=False)
        
        msg = MIMEMultipart()
        msg['Subject'] = f"🛡️ TOUTA FER - BACKUP - {datetime.now().strftime('%d/%m/%Y')}"
        msg['From'] = st.secrets["gmail"]["email_envoi"]
        msg['To'] = st.secrets["gmail"]["email_dest"]
        msg.attach(MIMEText(f"Sauvegarde complète (Stock, Réceptions, Ventes, Caisse, Audit) demandée par {user_nom}."))

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

# --- 5. GESTION DE LA SESSION & CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown(f"<p style='text-align:center; color:grey;'>{db_status}</p>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Identifiez-vous pour accéder à la gestion du stock et de la caisse.</p>", unsafe_allow_html=True)
    
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

    menu = ["📦 État des Stocks", "🛒 Nouvelle Vente", "💳 Suivi des Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
        menu.insert(1, "🚚 Réception Fer")
    if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant", "Comptable"]:
        menu.append("💰 Caisse & Trésorerie")
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Gestion Personnel", "📜 Historique Audit"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK (FORMAT PDF OFFICIEL) ---
    if choice == "📦 État des Stocks":
        st.header("📦 État du Stock (Catalogue Complet)")
        try:
            res_s = sb.table("stock").select("*").execute()
            df_s = formater_dataframe_stock(res_s.data if res_s.data else [])
            
            if not df_s.empty:
                search_q = st.text_input("🔍 Rechercher une référence ou désignation (ex: ROND A BETON, T.155, POINTE...)").strip().upper()
                df_aff = df_s.drop(columns=["Clé_Interne"])
                if search_q:
                    df_aff = df_aff[df_aff["Référence"].str.upper().str.contains(search_q) | df_aff["Désignation"].str.upper().str.contains(search_q)]
                
                st.dataframe(df_aff, use_container_width=True, hide_index=True)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total FDX Initial", f"{df_aff['FDX Initial'].sum():,.2f}")
                c2.metric("Total FDX Entrée", f"{df_aff['FDX Entrée'].sum():,.2f}")
                c3.metric("Total FDX Sortie", f"{df_aff['FDX Sortie'].sum():,.2f}")
                c4.metric("Total FDX Final", f"{df_aff['FDX Final'].sum():,.2f}")
            else:
                st.info("Chargement du stock initial...")

            if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
                with st.expander("⚙️ Options avancées du Stock"):
                    if st.button("🔄 Réinitialiser avec les valeurs exactes de la feuille PDF (28/10/2026)"):
                        synchroniser_stock_pdf(forcer=True)
                        log_action(user['nom'], "STOCK : Réinitialisation aux valeurs du PDF")
                        st.success("Stock synchronisé avec la feuille PDF !")
                        st.rerun()
        except Exception as e:
            st.error(f"Impossible de lire les stocks : {e}")

    # --- ONGLET : RÉCEPTION DE FER & ARTICLES ---
    elif choice == "🚚 Réception Fer":
        st.header("🚚 Réception de Marchandise & Suivi des Prix d'Achat")
        try:
            res_s = sb.table("stock").select("*").execute()
            df_s = formater_dataframe_stock(res_s.data if res_s.data else [])
            liste_articles = df_s["Clé_Interne"].tolist() if not df_s.empty else []
            
            col1, col2 = st.columns(2)
            fournisseur = col1.text_input("Usine / Fournisseur (ex: Tosyali, Bellara)").strip().replace("|", "-")
            bon_livraison = col1.text_input("N° Bon de Livraison / Camion").strip().replace("|", "-")
            
            article_choisi = col2.selectbox("Article reçu (Référence | Désignation | UM)", liste_articles)
            qte_recue = col2.number_input("Quantité reçue (FDX Entrée)", min_value=0.001, format="%.3f")
            
            prix_achat = st.number_input("Prix d'Achat Unitaire (en Centimes)", min_value=0.0, step=1000.0)
            total_achat = qte_recue * prix_achat
            
            st.subheader(f"💰 Coût Total de l'arrivage : {total_achat:,.0f} Centimes")
            
            if st.button("📥 VALIDER LA RÉCEPTION ET LE PRIX D'ACHAT", use_container_width=True):
                if not fournisseur:
                    st.error("Veuillez indiquer le nom du fournisseur ou de l'usine.")
                elif prix_achat <= 0:
                    st.error("Veuillez indiquer le prix d'achat pour suivre vos coûts.")
                else:
                    old_q = float(df_s.loc[df_s['Clé_Interne']==article_choisi, 'FDX Final'].values[0])
                    new_q = old_q + qte_recue
                    sb.table("stock").update({"quantite": new_q}).eq("diametre", article_choisi).execute()
                    
                    nom_court = article_choisi.replace(" | ", " - ")
                    details_rec = f"RÉCEPTION | {fournisseur} | {bon_livraison} | {nom_court} | {qte_recue:.3f} | {prix_achat:,.0f} | {total_achat:,.0f}"
                    log_action(user['nom'], details_rec)
                    
                    if fb:
                        fb.collection("receptions_backup").add({
                            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "fournisseur": fournisseur, "bon": bon_livraison,
                            "article": nom_court, "quantite": qte_recue,
                            "prix_unitaire_centimes": prix_achat, "cout_total_centimes": total_achat,
                            "par": user['nom']
                        })
                    st.success(f"✅ Réception enregistrée ! Nouveau stock : {new_q:,.3f}")
                    st.balloons()
            
            st.divider()
            st.subheader("📊 Historique détaillé des Achats et Fluctuation des Prix")
            res_l = sb.table("logs").select("*").order("id", desc=True).execute()
            df_receptions = extraire_tableau_receptions(res_l.data if res_l.data else [])
            
            if not df_receptions.empty:
                articles_dispo = ["Tous les articles"] + sorted(df_receptions["Article"].unique().tolist())
                filtre_art = st.selectbox("🔍 Filtrer par article pour comparer les prix d'achat :", articles_dispo)
                if filtre_art != "Tous les articles":
                    df_receptions = df_receptions[df_receptions["Article"] == filtre_art]
                st.dataframe(df_receptions, use_container_width=True, hide_index=True)
            else:
                st.info("Aucune réception détaillée enregistrée pour le moment.")
        except Exception as e:
            st.error(f"Erreur lors de l'accès aux réceptions : {e}")

    # --- VENTES (CENTIMES + CONTACT) ---
    elif choice == "🛒 Nouvelle Vente":
        st.header("🛒 Nouvelle Vente (FDX Sortie)")
        res_s = sb.table("stock").select("*").execute()
        df_s = formater_dataframe_stock(res_s.data if res_s.data else [])
        liste_articles = df_s["Clé_Interne"].tolist() if not df_s.empty else []

        col1, col2 = st.columns(2)
        cl = col1.text_input("Nom du Client").strip()
        tel = col1.text_input("Contact Client (Tél/Email)").strip()
        f = col2.selectbox("Article vendu (Réf | Désignation | UM)", liste_articles)
        
        stock_dispo = float(df_s.loc[df_s['Clé_Interne']==f, 'FDX Final'].values[0]) if not df_s.empty and f else 0.0
        col2.caption(f"Stock disponible : **{stock_dispo:,.3f}**")
        
        q_v = col2.number_input("Quantité vendue (FDX Sortie)", min_value=0.001, format="%.3f")
        px = col1.number_input("Prix de Vente Unitaire (Centimes)", min_value=0.0)
        
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
                    if stock_dispo >= q_v:
                        dv = {"date":str(date.today()), "client":cl, "contact":tel, "fer":f, "qte":q_v, "total":total, "paye":avance, "reste":total-avance, "echeance":date_e, "vendeur":user['nom']}
                        sb.table("ventes").insert(dv).execute()
                        sb.table("stock").update({"quantite": stock_dispo - q_v}).eq("diametre", f).execute()
                        if fb: fb.collection("ventes_backup").add(dv)
                        log_action(user['nom'], f"VENTE : {q_v} de [{f}] à {cl} (Prix/U: {px:,.0f} | Reste: {total-avance:,.0f})")
                        st.success("Vente enregistrée et déduite du stock !")
                        st.balloons()
                    else: st.error(f"Stock insuffisant ({stock_dispo:,.3f} disponible).")
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

    # --- NOUVEL ONGLET : CAISSE & TRÉSORERIE ---
    elif choice == "💰 Caisse & Trésorerie":
        st.header("💰 Gestion de la Caisse & Trésorerie (en Centimes)")
        try:
            res_v = sb.table("ventes").select("*").execute()
            df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
            
            res_l = sb.table("logs").select("*").order("id", desc=True).execute()
            df_caisse = extraire_tableau_caisse(res_l.data if res_l.data else [])
            
            # Calculs financiers automatiques
            encaissements_ventes = float(df_v['paye'].sum()) if not df_v.empty and 'paye' in df_v else 0.0
            credits_dehors = float(df_v['reste'].sum()) if not df_v.empty and 'reste' in df_v else 0.0
            
            entrees_manuelles = float(df_caisse[df_caisse['Sens'] == '🟢 Entrée']['Montant_Num'].sum()) if not df_caisse.empty else 0.0
            sorties_depenses = float(df_caisse[df_caisse['Sens'] == '🔴 Sortie']['Montant_Num'].sum()) if not df_caisse.empty else 0.0
            
            solde_net_caisse = (encaissements_ventes + entrees_manuelles) - sorties_depenses
            
            # Affichage des compteurs professionnels
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💵 Encaissé (Ventes & Crédits)", f"{encaissements_ventes:,.0f} Cts")
            m2.metric("➕ Apports Caisse", f"{entrees_manuelles:,.0f} Cts")
            m3.metric("🔴 Sorties & Dépenses", f"{sorties_depenses:,.0f} Cts")
            m4.metric("🏦 SOLDE NET EN CAISSE", f"{solde_net_caisse:,.0f} Cts")
            
            st.info(f"⏳ **Total des Crédits Clients dehors (Reste à recouvrer) :** {credits_dehors:,.0f} Centimes")
            st.divider()
            
            # Formulaire simple pour ajouter une opération de caisse
            with st.expander("➕ Enregistrer une Opération de Caisse (Dépense, Paiement Fournisseur, Apport...)", expanded=True):
                c1, c2, c3 = st.columns(3)
                sens_op = c1.radio("Type de mouvement", ["🔴 Sortie", "🟢 Entrée"])
                
                if sens_op == "🔴 Sortie":
                    cat_list = ["Paiement Fournisseur / Usine", "Transport / Camion", "Salaires / Avances Employés", "Gasoil / Entretien", "Frais Généraux (Factures, Repas...)", "Retrait Patron"]
                else:
                    cat_list = ["Apport en Caisse (Fond de caisse)", "Autre Entrée d'argent"]
                    
                cat_op = c2.selectbox("Catégorie", cat_list)
                mode_op = c3.selectbox("Mode de règlement", ["Espèces (Cash)", "Chèque", "Virement Bancaire"])
                
                c4, c5 = st.columns([1, 2])
                montant_op = c4.number_input("Montant (en Centimes)", min_value=0.0, step=1000.0)
                motif_op = c5.text_input("Détail / Bénéficiaire (ex: Chauffeur Ahmed, Usine Tosyali...)").strip().replace("|", "-")
                
                if st.button("💾 VALIDER L'OPÉRATION DE CAISSE", use_container_width=True):
                    if montant_op <= 0:
                        st.error("Veuillez saisir un montant supérieur à 0.")
                    elif not motif_op:
                        st.error("Veuillez préciser le détail ou le bénéficiaire.")
                    else:
                        log_txt = f"CAISSE | {sens_op} | {cat_op} | {mode_op} | {montant_op:.0f} | {motif_op}"
                        log_action(user['nom'], log_txt)
                        if fb:
                            fb.collection("caisse_backup").add({
                                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "sens": sens_op, "categorie": cat_op, "mode": mode_op,
                                "montant_centimes": montant_op, "motif": motif_op, "par": user['nom']
                            })
                        st.success("✅ Mouvement de caisse enregistré avec succès !")
                        st.rerun()
            
            st.divider()
            st.subheader("📖 Livre de Caisse Détaillé (Historique des Entrées & Dépenses)")
            if not df_caisse.empty:
                filtre_sens = st.radio("Afficher :", ["Toutes les opérations", "🔴 Sorties & Dépenses uniquement", "🟢 Entrées uniquement"], horizontal=True)
                df_caisse_aff = df_caisse.drop(columns=["Montant_Num"])
                if "Sorties" in filtre_sens:
                    df_caisse_aff = df_caisse_aff[df_caisse_aff["Sens"] == "🔴 Sortie"]
                elif "Entrées" in filtre_sens:
                    df_caisse_aff = df_caisse_aff[df_caisse_aff["Sens"] == "🟢 Entrée"]
                st.dataframe(df_caisse_aff, use_container_width=True, hide_index=True)
            else:
                st.info("Aucune dépense ou opération manuelle enregistrée dans la caisse pour le moment.")
        except Exception as e:
            st.error(f"Erreur dans le module Caisse : {e}")

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