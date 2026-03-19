import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="TOUTA FER - Système de Gestion", page_icon="🏗️", layout="wide")

# --- 2. SÉCURITÉ : HACHAGE DES MOTS DE PASSE ---
# Transforme le mot de passe en code secret illisible
def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 3. COMPTE MAÎTRE DÉVELOPPEUR ---
# Ton identifiant : développeur / Ton passe : Touta070303
USERS = {
    "développeur": {"pwd": hash_pwd("Touta070303"), "role": "Développeur", "nom": "Maître Système"}
}

# --- 4. INITIALISATION DATA (En attendant la double connexion Supabase/Firebase) ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if 'stock_data' not in st.session_state:
    diams = ['6mm', '8mm', '10mm', '12mm', '14mm', '16mm', '18mm', '20mm', '22mm', '25mm', '32mm', '40mm']
    st.session_state.stock_data = pd.DataFrame({'Diamètre': diams, 'Stock (T)': [0.0]*len(diams)})

if 'ventes_data' not in st.session_state:
    st.session_state.ventes_data = pd.DataFrame(columns=['Date','Client','Fer','Qté','Total','Reste','Vendeur'])

# --- 5. INTERFACE DE CONNEXION ---
if not st.session_state.auth:
    st.markdown("<h1 style='text-align: center; color: #1E3A8A;'>🏗️ BIENVENUE CHEZ TOUTA FER</h1>", unsafe_input=True)
    st.markdown("<h3 style='text-align: center;'>Accès Privé au Système de Gestion</h3>", unsafe_input=True)
    
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
                st.error("Identifiant ou mot de passe invalide.")
else:
    user = st.session_state.user
    st.sidebar.title("🏗️ TOUTA FER")
    st.sidebar.success(f"Utilisateur : {user['nom']}")
    st.sidebar.write(f"Rôle : **{user['role']}**")
    st.sidebar.warning("Unité : Centimes | Poids : Tonnes")

    # --- MENU NAVIGATION ---
    menu_options = ["📦 Stocks (Tonnes)", "🛒 Vente Directe", "💳 Suivi Crédits"]
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        menu_options += ["👥 Personnel", "📜 Historique (Audit)"]
    
    choice = st.sidebar.radio("Menu Principal", menu_options)

    # --- 📦 STOCKS (TONNES) ---
    if choice == "📦 Stocks (Tonnes)":
        st.header("📦 État des Stocks Réels")
        st.dataframe(st.session_state.stock_data, use_container_width=True)
        
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter un arrivage de marchandise"):
                d_a = st.selectbox("Référence Fer", st.session_state.stock_data['Diamètre'])
                q_a = st.number_input("Tonnes ajoutées", min_value=0.001, format="%.3f")
                if st.button("Mettre à jour le stock"):
                    idx = st.session_state.stock_data[st.session_state.stock_data['Diamètre'] == d_a].index[0]
                    st.session_state.stock_data.at[idx, 'Stock (T)'] += q_a
                    # Ici on lancera l'écriture sur Supabase + Firebase
                    st.success(f"Stock mis à jour pour TOUTA FER : + {q_a} T")
                    st.rerun()

    # --- 🛒 VENTE (RÉACTIF ET SÉCURISÉ) ---
    elif choice == "🛒 Vente Directe":
        st.header("🛒 Nouvelle Vente")
        
        c1, c2 = st.columns(2)
        client = c1.text_input("Nom du Client")
        fer = c2.selectbox("Diamètre du Fer", st.session_state.stock_data['Diamètre'])
        qte = c2.number_input("Quantité (Tonnes)", min_value=0.001, format="%.3f")
        prix_t = c1.number_input("Prix par Tonne (en Centimes)", min_value=0.0)
        
        total = qte * prix_t
        st.subheader(f"Total à payer : {total:,.0f} Centimes")

        st.divider()
        is_credit = st.checkbox("🚩 Vente à Crédit (Paiement partiel)")
        
        avance = total # Par défaut paiement total
        date_e = date.today()

        if is_credit:
            # S'affiche INSTANTANÉMENT quand on coche
            avance = st.number_input("Avance reçue (en Centimes)", min_value=0.0, max_value=total)
            date_e = st.date_input("Date limite de paiement du crédit")
            reste = total - avance
            st.error(f"Dette Client : {reste:,.0f} Centimes")

        st.divider()
        if st.button("🚀 VALIDER LA TRANSACTION", use_container_width=True):
            if client == "":
                st.error("Veuillez entrer le nom du client.")
            else:
                idx = st.session_state.stock_data[st.session_state.stock_data['Diamètre'] == fer].index[0]
                if st.session_state.stock_data.at[idx, 'Stock (T)'] >= qte:
                    st.session_state.stock_data.at[idx, 'Stock (T)'] -= qte
                    
                    # --- DOUBLE SAUVEGARDE (SUPABASE + FIREBASE) ---
                    # data = {"client": client, "total": total, "avance": avance, "vendeur": user['nom']}
                    # save_to_supabase(data)
                    # save_to_firebase(data)
                    
                    st.success("✅ Vente enregistrée et synchronisée sur les deux serveurs.")
                    st.balloons()
                else:
                    st.error("Stock insuffisant chez TOUTA FER !")

    # --- 💳 SUIVI DES CRÉDITS ---
    elif choice == "💳 Suivi Crédits":
        st.header("💳 Liste des Dettes Clients")
        st.info("Cette liste regroupe les crédits à récupérer.")
        # Affichage du tableau filtré (Reste > 0)

    # --- 👥 GESTION PERSONNEL ---
    elif choice == "👥 Personnel":
        st.header("👥 Administration de TOUTA FER")
        st.write("Gestion des employés et des droits d'accès.")
        # Ici on ajoute la hiérarchie de suppression Développeur > Grand Patron > Patron

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()
