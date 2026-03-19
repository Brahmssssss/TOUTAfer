import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# --- CONNEXION À LA BASE DE DONNÉES ---
conn = sqlite3.connect('entreprise_fer_dz.db', check_same_thread=False)
c = conn.cursor()

# Création des tables
c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, nom TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS stock (diametre TEXT PRIMARY KEY, quantite REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS ventes (id INTEGER PRIMARY KEY, date TEXT, client TEXT, contact TEXT, fer TEXT, qte REAL, total REAL, paye REAL, reste REAL, echeance TEXT, vendeur TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, date TEXT, utilisateur TEXT, action TEXT)''')

# Initialisation du compte DÉVELOPPEUR MAÎTRE
c.execute("SELECT * FROM users WHERE username='développeur'")
if not c.fetchone():
    c.execute("INSERT INTO users (username, password, role, nom) VALUES ('développeur', 'Touta070303', 'Développeur', 'Développeur Système')")
    # Liste complète des diamètres de fer à béton (6mm à 40mm)
    diametres = ['6mm', '8mm', '10mm', '12mm', '14mm', '16mm', '20mm', '25mm', '32mm', '40mm']
    for d in diametres:
        c.execute("INSERT OR IGNORE INTO stock (diametre, quantite) VALUES (?, 0.0)", (d,))
    conn.commit()

def log_action(user, action):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO logs (date, utilisateur, action) VALUES (?, ?, ?)", (now, user, action))
    conn.commit()

def format_dz(montant_da, mode):
    if mode == "Centimes":
        return f"{montant_da * 100:,.0f} Centimes"
    else:
        return f"{montant_da:,.2f} DA"

# --- INTERFACE ---
st.sidebar.title("🇩🇿 Gestion Fer à Béton (Tonnes)")
unite_prefere = st.sidebar.radio("Unité monétaire :", ["Dinar (DA)", "Centimes"])

if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🏗️ Accès Entreprise")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        c.execute("SELECT username, role, nom FROM users WHERE username=? AND password=?", (u, p))
        user_data = c.fetchone()
        if user_data:
            st.session_state.auth = True
            st.session_state.user = {"username": user_data[0], "role": user_data[1], "nom": user_data[2]}
            st.rerun()
        else:
            st.error("Identifiants incorrects")
else:
    user = st.session_state.user
    st.sidebar.write(f"Connecté : **{user['nom']}**")
    st.sidebar.info(f"Rôle : {user['role']}")
    
    if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
        tabs = ["📦 Stock (Tonnes)", "🛒 Vente", "💳 Crédits", "👥 Personnel", "📜 Historique"]
    else:
        tabs = ["📦 Stock (Tonnes)", "🛒 Vente", "💳 Crédits"]
    
    choice = st.sidebar.radio("Menu", tabs)

    # --- 📦 STOCK (EN TONNES) ---
    if choice == "📦 Stock (Tonnes)":
        st.header("📦 État des Stocks (en Tonnes)")
        st_data = pd.read_sql("SELECT * FROM stock", conn)
        st.dataframe(st_data, use_container_width=True)
        
        if user['role'] in ["Développeur", "Grand Patron", "Patron", "Gérant"]:
            with st.expander("📥 Ajouter un arrivage de fer"):
                d = st.selectbox("Choisir le diamètre", st_data['diametre'])
                q = st.number_input("Nombre de Tonnes reçues", min_value=0.01, format="%.3f")
                if st.button("Enregistrer l'entrée"):
                    c.execute("UPDATE stock SET quantite = quantite + ? WHERE diametre = ?", (q, d))
                    conn.commit()
                    log_action(user['nom'], f"A ajouté {q} Tonnes de {d}")
                    st.success(f"Stock mis à jour : + {q} T")
                    st.rerun()

    # --- 🛒 VENTE (LOGIQUE CRÉDIT AMÉLIORÉE) ---
    elif choice == "🛒 Vente":
        st.header("🛒 Enregistrer une Vente")
        with st.form("vente_form"):
            col1, col2 = st.columns(2)
            cl = col1.text_input("Nom du Client / Entreprise")
            tel = col1.text_input("Téléphone")
            f = col2.selectbox("Référence Fer", pd.read_sql("SELECT diametre FROM stock", conn))
            q_v = col2.number_input("Quantité vendue (Tonnes)", min_value=0.001, format="%.3f")
            
            px_input = col1.number_input(f"Prix par Tonne ({unite_prefere})", min_value=0.0)
            
            st.divider()
            is_credit = st.checkbox("🚩 Vente à Crédit (Paiement partiel ou futur)")
            
            paye_input = 0.0
            date_e = date.today()
            
            if is_credit:
                paye_input = st.number_input(f"Avance versée aujourd'hui ({unite_prefere})", min_value=0.0)
                date_e = st.date_input("Date limite de paiement (Échéance)")
            
            if st.form_submit_button("🚀 Valider la Vente"):
                # Calculs en Dinars
                px_da = px_input / 100 if unite_prefere == "Centimes" else px_input
                total_da = q_v * px_da
                
                if not is_credit:
                    paye_da = total_da
                    reste_da = 0.0
                    date_e_str = date.today().strftime("%d/%m/%Y")
                else:
                    paye_da = paye_input / 100 if unite_prefere == "Centimes" else paye_input
                    reste_da = total_da - paye_da
                    date_e_str = date_e.strftime("%d/%m/%Y")
                
                # Vérification stock
                q_act = c.execute("SELECT quantite FROM stock WHERE diametre=?", (f,)).fetchone()[0]
                if q_act >= q_v:
                    c.execute("UPDATE stock SET quantite = quantite - ? WHERE diametre = ?", (q_v, f))
                    c.execute("INSERT INTO ventes (date, client, contact, fer, qte, total, paye, reste, echeance, vendeur) VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (date.today().strftime("%d/%m/%Y"), cl, tel, f, q_v, total_da, paye_da, reste_da, date_e_str, user['nom']))
                    conn.commit()
                    log_action(user['nom'], f"Vente: {q_v}T de {f} à {cl}. Crédit: {is_credit}")
                    st.success(f"Vente effectuée ! Total: {format_dz(total_da, unite_prefere)}")
                    if reste_da > 0:
                        st.warning(f"Reste à recouvrer : {format_dz(reste_da, unite_prefere)}")
                else:
                    st.error(f"Stock insuffisant ! Il reste seulement {q_act} Tonnes de {f}")

    # --- 💳 CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("💳 Suivi des Crédits Clients")
        creds = pd.read_sql("SELECT * FROM ventes WHERE reste > 0", conn)
        df_disp = creds.copy()
        if unite_prefere == "Centimes":
            for col in ['total', 'paye', 'reste']: df_disp[col] = df_disp[col] * 100
        st.dataframe(df_disp, use_container_width=True)
        
        if not creds.empty:
            st.divider()
            st.subheader("Encaisser un versement")
            id_v = st.selectbox("Sélectionner la Vente ID", creds['id'].tolist())
            mont_reb = st.number_input(f"Montant reçu ({unite_prefere})", min_value=0.0)
            if st.button("Valider le remboursement"):
                da_reb = mont_reb / 100 if unite_prefere == "Centimes" else mont_reb
                c.execute("UPDATE ventes SET paye = paye + ?, reste = reste - ? WHERE id = ?", (da_reb, da_reb, id_v))
                conn.commit()
                log_action(user['nom'], f"Encaissement crédit ID {id_v} de {da_reb} DA")
                st.rerun()

    # --- 👥 PERSONNEL (LOGIQUE HIÉRARCHIQUE) ---
    elif choice == "👥 Personnel":
        st.header("👥 Gestion des Accès")
        empl = pd.read_sql("SELECT username, role, nom FROM users", conn)
        st.table(empl)
        
        with st.expander("➕ Créer un nouveau compte"):
            n_nom = st.text_input("Nom complet")
            n_user = st.text_input("Login")
            n_pass = st.text_input("Pass", type="password")
            roles_p = ["Commercial", "Comptable", "Gérant", "Patron"]
            if user['role'] in ["Développeur", "Grand Patron"]: roles_p.append("Grand Patron")
            n_role = st.selectbox("Rôle", roles_p)
            if st.button("Créer"):
                c.execute("INSERT INTO users (username, password, role, nom) VALUES (?,?,?,?)", (n_user, n_pass, n_role, n_nom))
                conn.commit()
                log_action(user['nom'], f"Création compte {n_role}: {n_user}")
                st.rerun()

        if user['role'] in ["Développeur", "Grand Patron", "Patron"]:
            with st.expander("🗑️ Supprimer un compte"):
                if user['role'] == "Développeur":
                    l_s = [u for u in empl['username'].tolist() if u != user['username']]
                elif user['role'] == "Grand Patron":
                    l_s = [r['username'] for i, r in empl.iterrows() if r['role'] != 'Développeur' and r['username'] != user['username']]
                else: # Patron
                    l_s = [r['username'] for i, r in empl.iterrows() if r['role'] not in ['Développeur', 'Grand Patron', 'Patron']]
                
                u_to_del = st.selectbox("Compte à supprimer", l_s) if l_s else None
                if u_to_del and st.button("Supprimer définitivement"):
                    c.execute("DELETE FROM users WHERE username=?", (u_to_del,))
                    conn.commit()
                    log_action(user['nom'], f"Suppression de {u_to_del}")
                    st.rerun()

    # --- HISTORIQUE ---
    elif choice == "📜 Historique":
        st.header("📜 Historique des actions")
        logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC", conn)
        st.dataframe(logs, use_container_width=True)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
