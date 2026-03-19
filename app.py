import streamlit as st
import pandas as pd
import hashlib
from supabase import create_client

st.set_page_config(page_title="DIAGNOSTIC TOUTA FER")

# --- FONCTION DE NETTOYAGE ---
def clean(text):
    return text.strip().replace(" ", "").rstrip("/")

# --- TEST DE CONNEXION ---
st.title("🛠️ Diagnostic de Connexion")

try:
    URL = clean(st.secrets["supabase"]["url"])
    KEY = clean(st.secrets["supabase"]["key"])
    
    sb = create_client(URL, KEY)
    
    # On essaie de lire la table des utilisateurs
    res = sb.table("users").select("*").execute()
    st.success("✅ CONNEXION RÉUSSIE : L'application arrive à lire la base de données !")
    st.write(f"Nombre de comptes trouvés : {len(res.data)}")
    
    # Affichage des identifiants valides (pour vérifier les accents)
    if len(res.data) > 0:
        st.write("### Identifiants enregistrés :")
        for user in res.data:
            st.code(f"Identifiant : {user['username']}")

except Exception as e:
    st.error("❌ ÉCHEC DE CONNEXION")
    st.write(f"**Détails de l'erreur :** {e}")
    st.info("Vérifiez que l'URL et la Clé dans les Secrets de Streamlit sont correctes.")

# --- FORMULAIRE DE CONNEXION ---
st.divider()
st.subheader("Essayer de se connecter")

def hash_pwd(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

u = st.text_input("Identifiant")
p = st.text_input("Mot de passe", type="password")

if st.button("TESTER LA CONNEXION"):
    try:
        res = sb.table("users").select("*").eq("username", u).eq("password", hash_pwd(p)).execute()
        if res.data:
            st.balloons()
            st.success(f"Bravo {res.data[0]['nom']} ! Tu es connecté.")
        else:
            st.error("Identifiant ou mot de passe incorrect.")
            st.write(f"Ton mot de passe haché est : `{hash_pwd(p)}`")
    except:
        st.error("La base de données ne répond pas.")
