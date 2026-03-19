import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

# --- CONNEXION À LA BASE DE DONNÉES ---
conn = sqlite3.connect('entreprise_fer.db', check_same_thread=False)
c = conn.cursor()

# Création des tables
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, nom TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS stock 
             (diametre TEXT PRIMARY KEY, quantite INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS ventes 
             (id INTEGER PRIMARY KEY, date TEXT, client TEXT, contact TEXT, fer TEXT, 
              qte INTEGER, total REAL, paye REAL, reste REAL, echeance TEXT, vendeur TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS logs 
             (id INTEGER PRIMARY KEY, date TEXT, utilisateur TEXT, action TEXT)''')

# Création du premier compte Admin si la table est vide
c.execute("SELECT * FROM users WHERE username='admin'")
if not c.fetchone():
    c.execute("INSERT INTO users (username, password, role, nom) VALUES ('admin', 'admin123', 'Patron', 'Le Patron Principal')")
    for d in ['6mm', '8mm', '10mm', '12mm', '14mm', '16mm', '20mm']:
        c.execute("INSERT OR IGNORE INTO stock (diametre, quantite) VALUES (?, 0)", (d,))
    conn.commit()

def log_action(user, action):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO logs (date, utilisateur, action) VALUES (?, ?, ?)", (now, user, action))
    conn.commit()

# --- CONNEXION ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🏗️ Accès Entreprise Fer")
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
    st.sidebar.title(f"👤 {user['nom']}")
    st.sidebar.write(f"Rôle : **{user['role']}**")
    
    # --- NAVIGATION SELON LE RÔLE ---
    # Un compte créé avec le rôle "Patron" aura accès à TOUT automatiquement
    if user['role'] == "Patron":
        tabs = ["📦 Stock", "🛒 Ventes", "💳 Crédits", "👥 Gestion Personnel", "📜 Historique (Espion)"]
    elif user['role'] == "Gérant":
        tabs = ["📦 Stock", "🛒 Ventes", "💳 Crédits", "👥 Gestion Personnel"]
    else:
        tabs = ["📦 Stock", "🛒 Ventes", "💳 Crédits"]
    
    choice = st.sidebar.radio("Menu principal", tabs)

    # --- 👥 GESTION DU PERSONNEL (Patron & Gérant) ---
    if choice == "👥 Gestion Personnel":
        st.header("Gestion des accès")
        
        # Liste des comptes existants
        st.subheader("Comptes actuels")
        empl = pd.read_sql("SELECT username, role, nom FROM users", conn)
        st.table(empl)

        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("➕ Créer un nouveau compte")
            new_n = st.text_input("Prénom et Nom de l'employé")
            new_u = st.text_input("Identifiant (Login)")
            new_p = st.text_input("Mot de passe (Login)")
            # AJOUT DU RÔLE PATRON DANS LA LISTE
            new_r = st.selectbox("Attribuer un rôle", ["Commercial", "Comptable", "Gérant", "Patron"])
            
            if st.button("Enregistrer le nouveau compte"):
                if new_u and new_p and new_n:
                    c.execute("INSERT INTO users (username, password, role, nom) VALUES (?,?,?,?)", (new_u, new_p, new_r, new_n))
                    conn.commit()
                    log_action(user['nom'], f"A créé un compte {new_r} pour {new_n}")
                    st.success(f"Le compte de {new_n} a été créé avec succès en tant que {new_r} !")
                    st.rerun()
                else:
                    st.error("Veuillez remplir toutes les cases.")
        
        with col2:
            if user['role'] == "Patron":
                st.subheader("🗑️ Supprimer un compte")
                u_to_del = st.selectbox("Choisir le compte à effacer", empl['username'].tolist())
                if st.button("Confirmer la suppression"):
                    if u_to_del != "admin" and u_to_del != user['username']:
                        c.execute("DELETE FROM users WHERE username=?", (u_to_del,))
                        conn.commit()
                        log_action(user['nom'], f"A supprimé le compte de {u_to_del}")
                        st.warning(f"Le compte {u_to_del} a été supprimé.")
                        st.rerun()
                    else:
                        st.error("Vous ne pouvez pas supprimer le compte admin principal ou votre propre compte.")

    # --- 📦 GESTION DU STOCK ---
    elif choice == "📦 Stock":
        st.header("État des Stocks de Fer")
        st_data = pd.read_sql("SELECT * FROM stock", conn)
        st.dataframe(st_data, use_container_width=True)
        
        if user['role'] in ["Patron", "Gérant"]:
            with st.expander("📥 Ajouter un arrivage de marchandise"):
                d = st.selectbox("Diamètre du fer", st_data['diametre'])
                q = st.number_input("Nombre de barres reçues", min_value=1)
                if st.button("Valider l'entrée en stock"):
                    c.execute("UPDATE stock SET quantite = quantite + ? WHERE diametre = ?", (q, d))
                    conn.commit()
                    log_action(user['nom'], f"A ajouté {q} barres de {d}")
                    st.success("Stock mis à jour avec succès")
                    st.rerun()

    # --- 🛒 VENTES ---
    elif choice == "🛒 Ventes":
        st.header("Nouvelle Vente")
        with st.form("vente_form"):
            c1, c2 = st.columns(2)
            cl = c1.text_input("Nom du Client")
            tel = c1.text_input("Téléphone")
            f = c2.selectbox("Fer à béton", pd.read_sql("SELECT diametre FROM stock", conn))
            q_v = c2.number_input("Quantité vendue", min_value=1)
            px = c1.number_input("Prix Unitaire (FCFA)", min_value=0)
            paye = c2.number_input("Avance payée aujourd'hui", min_value=0)
            date_e = st.date_input("Date d'échéance (si crédit)")
            
            if st.form_submit_button("🛒 Valider la vente"):
                total = q_v * px
                reste = total - paye
                q_actuelle = c.execute("SELECT quantite FROM stock WHERE diametre=?", (f,)).fetchone()[0]
                
                if q_actuelle >= q_v:
                    c.execute("UPDATE stock SET quantite = quantite - ? WHERE diametre = ?", (q_v, f))
                    c.execute("INSERT INTO ventes (date, client, contact, fer, qte, total, paye, reste, echeance, vendeur) VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (date.today().strftime("%d/%m/%Y"), cl, tel, f, q_v, total, paye, reste, date_e.strftime("%d/%m/%Y"), user['nom']))
                    conn.commit()
                    log_action(user['nom'], f"Vente à {cl} : {q_v} barres de {f}. Reste: {reste} FCFA")
                    st.success(f"Vente enregistrée ! Total: {total} FCFA. Reste: {reste} FCFA")
                else:
                    st.error("Stock insuffisant pour ce diamètre !")

    # --- 💳 CRÉDITS ---
    elif choice == "💳 Crédits":
        st.header("Suivi des Crédits Clients")
        creds = pd.read_sql("SELECT * FROM ventes WHERE reste > 0", conn)
        st.dataframe(creds, use_container_width=True)
        
        if not creds.empty:
            st.subheader("Encaisser un reste à payer")
            id_v = st.selectbox("Choisir la vente (ID)", creds['id'].tolist())
            montant = st.number_input("Montant remboursé par le client", min_value=0)
            if st.button("Valider le paiement du crédit"):
                c.execute("UPDATE ventes SET paye = paye + ?, reste = reste - ? WHERE id = ?", (montant, montant, id_v))
                conn.commit()
                log_action(user['nom'], f"A encaissé {montant} FCFA pour la vente ID {id_v}")
                st.success("Le crédit a été mis à jour !")
                st.rerun()

    # --- 📜 HISTORIQUE (Patron seulement) ---
    elif choice == "📜 Historique (Espion)":
        st.header("Historique des actions (Qui a fait quoi ?)")
        logs = pd.read_sql("SELECT * FROM logs ORDER BY id DESC", conn)
        st.dataframe(logs, use_container_width=True)
        
        if st.button("🗑️ Effacer l'historique"):
            c.execute("DELETE FROM logs")
            conn.commit()
            st.rerun()

    if st.sidebar.button("Se déconnecter"):
        st.session_state.auth = False
        st.rerun()
