import streamlit as st
import sqlite3
import hashlib
import json
import urllib.request
import phonenumbers
from babel.numbers import format_currency

# Configuration de la page
st.set_page_config(page_title="AvisExpress 🚀", page_icon="🚀", layout="wide")

# Clés API FedaPay
FEDAPAY_SECRET_KEY = "sk_sandbox_..." # Remplace par ta clé secrète FedaPay (sk_live_... en production)
FEDAPAY_PUBLIC_KEY = "pk_sandbox_FZyFKQIh6gvCBSk6aShpSV7c"

# --- BASE DE DONNÉES ---
def get_db_connection():
    conn = sqlite3.connect("avisexpress_v2.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    mot_de_passe TEXT NOT NULL,
                    plan TEXT DEFAULT 'STANDARD',
                    nom_commerce TEXT DEFAULT 'Mon Commerce',
                    lien_google TEXT DEFAULT 'https://g.page/r/example/review',
                    message_custom TEXT DEFAULT 'Bonjour ! Merci pour votre visite chez {nom_commerce}. Laissez-nous un avis ici : {lien_google}'
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS envois (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    telephone TEXT NOT NULL,
                    date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES utilisateurs (id)
                )''')
    conn.commit()
    conn.close()

init_db()

# --- FONCTION DE VÉRIFICATION DE TRANSACTION BANCAIRE / MOBILE MONEY ---
def verifier_transaction_fedapay(transaction_id):
    """Interroge l'API FedaPay pour vérifier si la banque/mobile money a réellement validé le débit"""
    try:
        url = f"https://api.fedapay.com/v1/transactions/{transaction_id}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {FEDAPAY_SECRET_KEY}")
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            # Statut "approved" signifie que le compte a bien été débité
            status = res_data.get("v1/transaction", {}).get("status")
            return status == "approved"
    except Exception as e:
        return False

# --- SESSIONS & AUTHENTIFICATION ---
if "user" not in st.session_state:
    st.session_state.user = None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def enregistrer_utilisateur(email, password):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO utilisateurs (email, mot_de_passe) VALUES (?, ?)", (email, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verifier_identifiants(email, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM utilisateurs WHERE email = ? AND mot_de_passe = ?", (email, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user

def mettre_a_jour_plan(user_id, nouveau_plan):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE utilisateurs SET plan = ? WHERE id = ?", (nouveau_plan, user_id))
    conn.commit()
    conn.close()

# --- RETOUR DE PAIEMENT AUTOMATIQUE ---
query_params = st.query_params
if "id" in query_params and st.session_state.user:
    trans_id = query_params["id"]
    target_plan = query_params.get("plan", "PRO")
    
    # Vérification bancaire obligatoire avant attribution du plan
    if verifier_transaction_fedapay(trans_id):
        mettre_a_jour_plan(st.session_state.user["id"], target_plan)
        st.success(f"🎉 Paiement confirmé par la banque/mobile money ! Votre compte a été mis à niveau vers la formule {target_plan}.")
        st.query_params.clear()
        st.rerun()
    else:
        st.error("❌ Le paiement a échoué ou a été refusé par votre banque / operateur mobile money. Votre compte reste en version Gratuit/Standard.")
        st.query_params.clear()

# --- PAGE DE CONNEXION / INSCRIPTION ---
if not st.session_state.user:
    st.title("AvisExpress 🚀")
    st.subheader("Plateforme SaaS de collecte d'avis Google")
    
    tab_login, tab_signup = st.tabs(["🔐 Connexion", "📝 Inscription"])
    
    with tab_login:
        email = st.text_input("Adresse e-mail")
        password = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            user = verifier_identifiants(email, password)
            if user:
                st.session_state.user = dict(user)
                st.rerun()
            else:
                st.error("Identifiants incorrects.")

    with tab_signup:
        new_email = st.text_input("Nouvelle adresse e-mail")
        new_password = st.text_input("Nouveau mot de passe", type="password")
        if st.button("Créer un compte"):
            if enregistrer_utilisateur(new_email, new_password):
                st.success("Compte créé avec succès ! Veuillez vous connecter.")
            else:
                st.error("Cet e-mail est déjà utilisé.")
    st.stop()

# --- DASHBOARD PRINCIPAL ---
user = st.session_state.user

# Sidebar
st.sidebar.markdown(f"👤 Connecté : **{user['email']}**")
if st.sidebar.button("Déconnexion"):
    st.session_state.user = None
    st.rerun()

# Récupération du plan réel enregistré en BDD
conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT plan FROM utilisateurs WHERE id = ?", (user["id"],))
plan_actuel = c.fetchone()["plan"]
conn.close()

st.title("AvisExpress 🚀")
st.write(f"### Formule actuelle : **{plan_actuel}**")

tab1, tab2 = st.tabs(["📲 Envoi de SMS", "💳 Abonnement & Offres"])

with tab1:
    st.header("Envoyer une demande d'avis")
    if plan_actuel == "STANDARD":
        st.info("ℹ️ Vous êtes sur la formule Gratuite/Standard. Passez à la formule PRO ou EXPERT pour débloquer les SMS illimités.")
    else:
        st.success(f"Accès illimité actif (Plan {plan_actuel})")

with tab2:
    st.header("Formules d'abonnement")
    
    col1, col2 = st.columns(2)
    
    # --- PLAN PRO ---
    with col1:
        st.subheader("🌟 Formule PRO")
        st.write("• SMS illimités")
        st.write("• Statistiques de performance")
        st.write("• Support prioritaire par e-mail")
        st.write("**Tarif : 15 000 XOF / mois**")
        
        if plan_actuel == "PRO":
            st.success("✅ Formule PRO actuellement active sur votre compte.")
        else:
            st.warning("⚠️ Vous n'avez pas encore procédé au paiement pour cette formule.")
            
            # Bouton de paiement officiel FedaPay
            fedapay_pro_html = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="pay-btn-pro" style="background-color: #007bff; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                💳 Procéder au paiement (15 000 XOF)
            </button>
            <script>
                let widgetPro = FedaPay.init('#pay-btn-pro', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{
                        amount: 15000,
                        description: "Abonnement Formule PRO AvisExpress"
                    }},
                    customer: {{
                        email: "{user['email']}"
                    }},
                    onComplete: function(response) {{
                        if (response.reason === FedaPay.CHECKOUT_COMPLETED) {{
                            window.location.href = window.location.origin + "?id=" + response.transaction.id + "&plan=PRO";
                        }}
                    }}
                }});
            </script>
            '''
            st.components.v1.html(fedapay_pro_html, height=80)

    # --- PLAN EXPERT ---
    with col2:
        st.subheader("👑 Formule EXPERT")
        st.write("• Tout le contenu du plan PRO")
        st.write("• Multi-boutiques & Multi-utilisateurs")
        st.write("• Support VIP 24/7 par téléphone")
        st.write("**Tarif : 30 000 XOF / mois**")
        
        if plan_actuel == "EXPERT":
            st.success("✅ Formule EXPERT actuellement active sur votre compte.")
        else:
            st.warning("⚠️ Vous n'avez pas encore procédé au paiement pour cette formule.")
            
            # Bouton de paiement officiel FedaPay
            fedapay_expert_html = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="pay-btn-expert" style="background-color: #28a745; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                💳 Procéder au paiement (30 000 XOF)
            </button>
            <script>
                let widgetExpert = FedaPay.init('#pay-btn-expert', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{
                        amount: 30000,
                        description: "Abonnement Formule EXPERT AvisExpress"
                    }},
                    customer: {{
                        email: "{user['email']}"
                    }},
                    onComplete: function(response) {{
                        if (response.reason === FedaPay.CHECKOUT_COMPLETED) {{
                            window.location.href = window.location.origin + "?id=" + response.transaction.id + "&plan=EXPERT";
                        }}
                    }}
                }});
            </script>
            '''
            st.components.v1.html(fedapay_expert_html, height=80)
