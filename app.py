import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="TOUTA FER", page_icon="🏗️", layout="wide")

# --- 2. SÉCURITÉ : HACHAGE DES MOTS DE PASSE ---
def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 3. COMPTE MAÎTRE ---
# Identifiant : développeur / Mot de passe : Touta070303
USERS = {
    "développeur": {"pwd": hash_pwd("Touta070303"), "role": "Développeur", "nom": "Maître Système"}
}

# --- 4. INITIALISATION DES DONNÉES ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if 'stock_data' not in st.session_state:
    diams = ['6mm', '8mm', '10mm', '12mm', '14mm', '16mm', '18mm', '20mm', '22mm', '25mm', '32mm', '40mm']
    st.session_state.stock_data = pd.DataFrame({'Diamètre': diams, 'Stock (T)': [0.0]*len(diams)})

# --- 5. INTERFACE DE CONNEXION ---
if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ TOUTA FER</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Système de Gestion Privé</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        u_input = st.text_input("Identifiant")
        p_input = st.text_input("Mot de passe", type="password")
        if st.button("SE CONNECTER", use_container_width=True):
            if u_input in USERS and USERS[u_input]["pwd"] == hash_pwd(p_input):
                st.session_state.auth = True
                st.session_state.user = USERS[u_input]
                st.rerun()
            else:
                st.error("Identifiant ou mot de passe incorrect.")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.write(f"Utilisateur : **{user['nom']}**")
    st.sidebar.info(f"Rôle : {user['role']}")

    menu = ["📦 Stocks (Tonnes)", "🛒 Vente Directe", "💳 Suivi Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu += ["👥 Personnel", "📜 Historique"]
    
    choice = st.sidebar.radio("Navigation", menu)

    # --- STOCK ---
    if choice == "📦 Stocks (Tonnes)":
        st.header("État des Stocks (en Tonnes)")
        st.dataframe(st.session_state.stock_data, use_container_width=True)
        
        if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
            with st.expander("📥 Ajouter de la marchandise"):
                d = st.selectbox("Référence Fer", st.session_state.stock_data['Diamètre'])
                q = st.number_input("Tonnes", min_value=0.0, format="%.3f")
                if st.button("Valider l'ajout"):
                    idx = st.session_state.stock_data[st.session_state.stock_data['Diamètre'] == d].index[0]
                    st.session_state.stock_data.at[idx, 'Stock (T)'] += q
                    st.success("Stock mis à jour")
                    st.rerun()

    # --- VENTE ---
    elif choice == "🛒 Vente Directe":
        st.header("🛒 Nouvelle Vente (Centimes)")
        col1, col2 = st.columns(2)
        client = col1.text_input("Nom Client")
        fer = col2.selectbox("Fer", st.session_state.stock_data['Diamètre'])
        qte = col2.number_input("Tonnes", min_value=0.001, format="%.3f")
        prix = col1.number_input("Prix / Tonne (Centimes)", min_value=0.0)
        
        total = qte * prix
        st.subheader(f"Total : {total:,.0f} Centimes")
        
        is_credit = st.checkbox("🚩 Vente à Crédit")
        avance = total
        if is_credit:
            avance = st.number_input("Avance reçue (Centimes)", min_value=0.0, max_value=total)
            st.warning(f"Dette : {total - avance:,.0f} Centimes")

        if st.button("🚀 VALIDER LA VENTE", use_container_width=True):
            idx = st.session_state.stock_data[st.session_state.stock_data['Diamètre'] == fer].index[0]
            if st.session_state.stock_data.at[idx, 'Stock (T)'] >= qte:
                st.session_state.stock_data.at[idx, 'Stock (T)'] -= qte
                st.success("Vente réussie !")
                st.balloons()
            else:
                st.error("Stock insuffisant !")

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
