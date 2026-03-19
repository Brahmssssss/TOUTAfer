import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime, date

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- 2. FONCTIONS DE SÉCURITÉ (Style Gmail) ---
def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def valider_securite(username, password):
    if len(password) < 6:
        return False, "❌ Minimum 6 caractères."
    if username.lower() == password.lower():
        return False, "❌ Le mot de passe ne peut pas être le nom d'utilisateur."
    if not any(char.isdigit() for char in password):
        return False, "❌ Il faut au moins un chiffre."
    if not any(char.isupper() for char in password):
        return False, "❌ Il faut au moins une MAJUSCULE."
    if not any(char.islower() for char in password):
        return False, "❌ Il faut au moins une minuscule."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "❌ Il faut au moins un caractère spécial (@, #, !, ...)."
    return True, ""

# --- 3. INITIALISATION DES DONNÉES (Session State) ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if 'users' not in st.session_state:
    st.session_state.users = pd.DataFrame([
        {"username": "développeur", "password": hash_pwd("Touta070303"), "role": "Développeur", "nom": "Maître Système"}
    ])

if 'stock_data' not in st.session_state:
    diams = ['6mm', '8mm', '10mm', '12mm', '14mm', '16mm', '18mm', '20mm', '22mm', '25mm', '32mm', '40mm']
    st.session_state.stock_data = pd.DataFrame({'Diamètre': diams, 'Stock (T)': [0.0]*len(diams)})

if 'ventes_data' not in st.session_state:
    st.session_state.ventes_data = pd.DataFrame(columns=['Date','Client','Contact','Fer','Qté','Total','Payé','Reste','Échéance','Vendeur'])

if 'historique' not in st.session_state:
    st.session_state.historique = pd.DataFrame(columns=['Date', 'Utilisateur', 'Action'])

def log_action(user, action):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    new_log = pd.DataFrame([{'Date': now, 'Utilisateur': user, 'Action': action}])
    st.session_state.historique = pd.concat([new_log, st.session_state.historique], ignore_index=True)

# --- 4. INTERFACE DE CONNEXION ---
if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Système de Gestion Commerciale</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        u_input = st.text_input("Identifiant")
        p_input = st.text_input("Mot de passe", type="password")
        if st.button("SE CONNECTER", use_container_width=True):
            user_f = st.session_state.users[st.session_state.users['username'] == u_input]
            if not user_f.empty and user_f.iloc[0]['password'] == hash_pwd(p_input):
                st.session_state.auth = True
                st.session_state.user = user_f.iloc[0].to_dict()
                log_action(st.session_state.user['nom'], "Connexion au système")
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
else:
    # --- INTERFACE CONNECTÉE ---
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Utilisateur : {user['nom']}")
    st.sidebar.write(f"Rôle : **{user['role']}**")
    st.sidebar.warning("Unité : Centimes | Poids : Tonnes")

    # Navigation par rôle
    menu = ["📦 Stocks (Tonnes)", "🛒 Nouvelle Vente", "💳 Liste des Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique Audit"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK ---
    if choice == "📦 Stocks (Tonnes)":
        st.header("📦 État des Stocks (Tonnes)")
        st.dataframe(st.session_state.stock_data, use_container_width=True)
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter de la marchandise"):
                d = st.selectbox("Référence Fer", st.session_state.stock_data['Diamètre'])
                q = st.number_input("Tonnes", min_value=0.001, format="%.3f")
                if st.button("Enregistrer"):
                    idx = st.session_state.stock_data[st.session_state.stock_data['Diamètre'] == d].index[0]
                    st.session_state.stock_data.at[idx, 'Stock (T)'] += q
                    log_action(user['nom'], f"Ajout de {q}T de fer {d}")
                    st.rerun()

    # --- VENTE (RÉACTIF) ---
    elif choice == "🛒 Nouvelle Vente":
        st.header("🛒 Enregistrer une Vente (Centimes)")
        col1, col2 = st.columns(2)
        client = col1.text_input("Nom Client")
        contact = col1.text_input("Téléphone")
        fer = col2.selectbox("Fer", st.session_state.stock_data['Diamètre'])
        qte = col2.number_input("Quantité (T)", min_value=0.001, format="%.3f")
        prix = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = qte * prix
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        date_e = date.today().strftime("%d/%m/%Y")

        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            date_e = st.date_input("Échéance du crédit").strftime("%d/%m/%Y")
            st.error(f"Dette Client : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE", use_container_width=True):
            if client == "": st.error("Entrez le nom du client")
            else:
                idx = st.session_state.stock_data[st.session_state.stock_data['Diamètre'] == fer].index[0]
                if st.session_state.stock_data.at[idx, 'Stock (T)'] >= qte:
                    st.session_state.stock_data.at[idx, 'Stock (T)'] -= qte
                    nouvelle_v = pd.DataFrame([{'Date': datetime.now().strftime("%d/%m/%Y"), 'Client': client, 'Contact': contact, 'Fer': fer, 'Qté': qte, 'Total': total, 'Payé': avance, 'Reste': total - avance, 'Échéance': date_e, 'Vendeur': user['nom']}])
                    st.session_state.ventes_data = pd.concat([nouvelle_v, st.session_state.ventes_data], ignore_index=True)
                    log_action(user['nom'], f"Vente à {client} : {qte}T de {fer}")
                    st.success("Vente réussie chez TOUTA FER !")
                    st.balloons()
                else: st.error("Stock insuffisant !")

    # --- CRÉDITS ---
    elif choice == "💳 Liste des Crédits":
        st.header("💳 Suivi des Crédits Clients")
        creds = st.session_state.ventes_data[st.session_state.ventes_data['Reste'] > 0]
        if creds.empty: st.info("Aucun crédit.")
        else:
            st.dataframe(creds, use_container_width=True)
            st.divider()
            cl_sel = st.selectbox("Client", creds['Client'].unique())
            montant = st.number_input("Montant reçu (Centimes)", min_value=0.0)
            if st.button("Confirmer remboursement"):
                idx = st.session_state.ventes_data[st.session_state.ventes_data['Client'] == cl_sel].index[0]
                st.session_state.ventes_data.at[idx, 'Payé'] += montant
                st.session_state.ventes_data.at[idx, 'Reste'] -= montant
                log_action(user['nom'], f"Encaissement {montant} de {cl_sel}")
                st.success("Mis à jour !")
                st.rerun()

    # --- PERSONNEL (AVEC SÉCURITÉ ET HIÉRARCHIE) ---
    elif choice == "👥 Personnel":
        st.header("👥 Gestion du Personnel")
        st.dataframe(st.session_state.users[['username', 'role', 'nom']], use_container_width=True)
        
        with st.expander("➕ Créer un compte sécurisé"):
            n_nom = st.text_input("Nom & Prénom")
            n_user = st.text_input("Login")
            n_pass = st.text_input("Passe", type="password")
            
            roles_p = ["Commercial", "Comptable", "Gérant", "Patron"]
            if user['role'] in ["Développeur", "Grand Patron"]: roles_p.append("Grand Patron")
            n_role = st.selectbox("Rôle", roles_p)
            
            if st.button("Créer l'employé"):
                v, msg = valider_securite(n_user, n_pass)
                if not v: st.error(msg)
                else:
                    new_u = pd.DataFrame([{"username": n_user, "password": hash_pwd(n_pass), "role": n_role, "nom": n_nom}])
                    st.session_state.users = pd.concat([st.session_state.users, new_u], ignore_index=True)
                    log_action(user['nom'], f"A créé un compte {n_role} pour {n_nom}")
                    st.success("Compte créé !")
                    st.rerun()

        with st.expander("🗑️ Supprimer un compte"):
            if user['role'] == "Développeur":
                l_s = [u for u in st.session_state.users['username'].tolist() if u != user['username']]
            elif user['role'] == "Grand Patron":
                l_s = [r['username'] for i, r in st.session_state.users.iterrows() if r['role'] != 'Développeur' and r['username'] != user['username']]
            elif user['role'] == "Patron":
                l_s = [r['username'] for i, r in st.session_state.users.iterrows() if r['role'] not in ['Développeur', 'Grand Patron', 'Patron']]
            else: l_s = []

            if l_s:
                u_to_del = st.selectbox("Compte à effacer", l_s)
                if st.button("Confirmer Suppression"):
                    st.session_state.users = st.session_state.users[st.session_state.users['username'] != u_to_del]
                    log_action(user['nom'], f"A supprimé le compte {u_to_del}")
                    st.rerun()

    # --- HISTORIQUE ---
    elif choice == "📜 Historique Audit":
        st.header("📜 Historique des actions (Espion)")
        st.dataframe(st.session_state.historique, use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
