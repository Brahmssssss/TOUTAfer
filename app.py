import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# --- CONNEXION À LA BASE DE DONNÉES ---
conn = sqlite3.connect('entreprise_fer.db', check_same_thread=False)
c = conn.cursor()

# Création des tables si elles n'existent pas
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, nom TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS stock 
             (diametre TEXT PRIMARY KEY, quantite INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS ventes 
             (id INTEGER PRIMARY KEY, date TEXT, client TEXT, contact TEXT, fer TEXT, 
              qte INTEGER, total REAL, paye REAL, reste REAL, echeance TEXT, vendeur TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, date TEXT, utilisateur TEXT, action TEXT)''')

# Créer le compte Patron par défaut s'il n'y a personne
c.execute("SELECT * FROM users WHERE username='admin'")
if not c.fetchone():
    c.execute("INSERT INTO users (username, password, role, nom) VALUES ('admin', 'admin123', 'Patron', 'Le Patron')")
    # Initialiser le stock par défaut
    for d in ['6mm', '8mm', '10mm', '12mm', '14mm', '16mm']:
        c.execute("INSERT OR IGNORE INTO stock (diametre, quantite) VALUES (?, 0)", (d,))
    conn.commit()

# --- FONCTIONS UTILES ---
def log_action(user, action):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO logs (date, utilisateur, action) VALUES (?, ?, ?)", (now, user, action))
    conn.commit()

# --- INTERFACE DE CONNEXION ---
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
    st.sidebar.title(f"Bonjour, {user['nom']}")
    st.sidebar.info(f"Rôle : {user['role']}")
    
    # --- NAVIGATION ---
    if user['role'] == "Patron":
        tabs = ["📦 Stock", "🛒 Ventes", "💳 Crédits", "👥 Employés", "📜 Historique"]
    elif user['role'] == "Gérant":
        tabs = ["📦 Stock", "🛒 Ventes", "💳 Crédits", "👥 Employés"]
    else:
        tabs = ["📦 Stock", "🛒 Ventes", "💳 Crédits"]
    
    choice = st.sidebar.radio("Menu", tabs)

    # --- 👥 GESTION DES EMPLOYÉS (Patron & Gérant) ---
    if choice == "👥 Employés":
        st.header("Gestion du personnel")
        
        # Liste des employés
        st.subheader("Liste des comptes")
        empl = pd.read_sql("SELECT username, role, nom FROM users", conn)
        st.dataframe(empl, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Ajouter un employé")
            new_u = st.text_input("Identifiant (Login)")
            new_p = st.text_input("Mot de passe (Login)")
            new_n = st.text_input("Prénom/Nom")
            new_r = st.selectbox("Rôle", ["Commercial", "Comptable", "Gérant"])
            if st.button("Créer le compte"):
                c.execute("INSERT INTO users (username, password, role, nom) VALUES (?,?,?,?)", (new_u, new_p, new_r, new_n))
                conn.commit()
                log_action(user['nom'], f"A créé le compte de {new_n} ({new_r})")
                st.success("Employé ajouté !")
                st.rerun()
        
        with col2:
            if user['role'] == "Patron": # Seul le patron peut supprimer
                st.subheader("🗑️ Supprimer un compte")
                u_to_del = st.selectbox("Choisir l'employé à supprimer", empl['username'].tolist())
                if st.button("Supprimer définitivement"):
                    if u_to_del != "admin":
                        c.execute("DELETE FROM users WHERE username=?", (u_to_del,))
                        conn.commit()
                        log_action(user['nom'], f"A supprimé le compte {u_to_del}")
                        st.warning("Compte supprimé")
                        st.rerun()

    # --- 📦 GESTION DU STOCK ---
    elif choice == "📦 Stock":
        st.header("État des Stocks")
        st_data = pd.read_sql("SELECT * FROM stock", conn)
        st.table(st_data)
        
        if user['role'] in ["Patron", "Gérant"]:
            with st.expander("Ajouter du Fer (Arrivage)"):
                d = st.selectbox("Diamètre", st_data['diametre'])
                q = st.number_input("Quantité", min_value=1)
                if st.button("Valider"):
                    c.execute("UPDATE stock SET quantite = quantite + ? WHERE diametre = ?", (q, d))
                    conn.commit()
                    log_action(user['nom'], f"A ajouté {q} barres de {d}")
                    st.success("Stock augmenté")
                    st.rerun()

    # --- 🛒 VENTES ---
    elif choice == "🛒 Ventes":
        st.header("Nouvelle Vente")
        with st.form("v"):
            c1, c2 = st.columns(2)
            cl = c1.text_input("Nom Client")
            tel = c1.text_input("Téléphone Client")
            f = c2.selectbox("Fer", pd.read_sql("SELECT diametre FROM stock", conn))
            q_v = c2.number_input("Qté", min_value=1)
            px = c1.number_input("Prix Unitaire", min_value=0)
            paye = c2.number_input("Montant versé aujourd'hui", min_value=0)
            date_e = st.date_input("Échéance si crédit")
            
            if st.form_submit_button("Confirmer la vente"):
                total = q_v * px
                reste = total - paye
                # Verif stock
                q_actuelle = c.execute("SELECT quantite FROM stock WHERE diametre=?", (f,)).fetchone()[0]
                if q_actuelle >= q_v:
                    c.execute("UPDATE stock SET quantite = quantite - ? WHERE diametre = ?", (q_v, f))
                    c.execute("INSERT INTO ventes (date, client, contact, fer, qte, total, paye, reste, echeance, vendeur) VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (date.today().strftime("%d/%m/%Y"), cl, tel, f, q_v, total, paye, reste, date_e.strftime("%d/%m/%Y"), user['nom']))
                    conn.commit()
                    log_action(user['nom'], f"Vente à {cl} ({q_v} barres de {f}). Reste: {reste}")
                    st.success("Vente réussie !")
                else:
                    st.error("Stock insuffisant !")

    # --- 💳 CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des dettes")
        creds = pd.read_sql("SELECT * FROM ventes WHERE reste > 0", conn)
        st.dataframe(creds)
        
        if not creds.empty:
            st.subheader("Encaisser un paiement")
            id_v = st.selectbox("ID de la vente", creds['id'].tolist())
            montant = st.number_input("Somme reçue", min_value=0)
            if st.button("Mettre à jour le crédit"):
                c.execute("UPDATE ventes SET paye = paye + ?, reste = reste - ? WHERE id = ?", (montant, montant, id_v))
                conn.commit()
                log_action(user['nom'], f"A encaissé {montant} pour la vente ID {id_v}")
                st.rerun()

    # --- 📜 HISTORIQUE (Patron seulement) ---
    elif choice == "📜 Historique":
        st.header("Journal de bord (Audit)")
        logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC", conn)
        st.table(logs)

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()
