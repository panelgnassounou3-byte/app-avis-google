import streamlit as st
import sqlite3
import hashlib
import json
import urllib.request
import pandas as pd
import phonenumbers
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="AvisExpress 🚀", page_icon="🚀", layout="wide")

# Clés API FedaPay (Sandbox par défaut, à remplacer par sk_live_... pour le mode de production)
FEDAPAY_SECRET_KEY = "sk_sandbox_..." 
FEDAPAY_PUBLIC_KEY = "pk_sandbox_FZyFKQIh6gvCBSk6aShpSV7c"

LIMITE_CREDITS_STANDARD = 5

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
                    nom_commerce TEXT DEFAULT 'Mon Salon de Coiffure',
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

# --- VÉRIFICATION TRANSACTION FEDAPAY ---
def verifier_transaction_fedapay(transaction_id):
    try:
        url = f"https://api.fedapay.com/v1/transactions/{transaction_id}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {FEDAPAY_SECRET_KEY}")
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            status = res_data.get("v1/transaction", {}).get("status")
            return status == "approved"
    except Exception:
        return False

# --- GESTION DE BASE DE DONNÉES ET AUTHENTIFICATION ---
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

def enregistrer_envoi(user_id, telephone):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO envois (user_id, telephone) VALUES (?, ?)", (user_id, telephone))
    conn.commit()
    conn.close()

def obtenir_statistiques(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM envois WHERE user_id = ?", (user_id,))
    total_envois = c.fetchone()["total"]
    
    c.execute("SELECT plan FROM utilisateurs WHERE id = ?", (user_id,))
    plan = c.fetchone()["plan"]
    conn.close()
    return total_envois, plan

# --- TRAITEMENT AUTOMATIQUE DU RETOUR DE PAIEMENT ---
query_params = st.query_params
if "id" in query_params and st.session_state.user:
    trans_id = query_params["id"]
    target_plan = query_params.get("plan", "PRO")
    
    if verifier_transaction_fedapay(trans_id):
        mettre_a_jour_plan(st.session_state.user["id"], target_plan)
        st.success(f"🎉 Paiement confirmé ! Votre compte est passé à la formule {target_plan}.")
        st.query_params.clear()
        st.rerun()
    else:
        st.error("❌ Échec de la vérification du paiement auprès de la banque / Mobile Money.")
        st.query_params.clear()

# --- INTERFACE CONNEXION / INSCRIPTION ---
if not st.session_state.user:
    st.title("AvisExpress 🚀")
    st.subheader("Plateforme SaaS de collecte automatique d'avis Google")
    
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

# --- ESPACE CLIENT CONNECTÉ ---
user = st.session_state.user
total_envois, plan_actuel = obtenir_statistiques(user["id"])

# Sidebar : Configuration de l'entreprise
st.sidebar.markdown(f"👤 Connecté : **{user['email']}**")
if st.sidebar.button("Déconnexion"):
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Paramètres Commerce")

nom_commerce = st.sidebar.text_input("Nom de votre commerce :", value=user.get("nom_commerce", "Mon Salon de Coiffure"))
lien_google = st.sidebar.text_input("Lien Google Maps :", value=user.get("lien_google", "https://g.page/r/example/review"))
msg_template = st.sidebar.text_area("Message SMS personnalisé :", value=user.get("message_custom", "Bonjour ! Merci pour votre visite chez {nom_commerce}. Laissez-nous un avis ici : {lien_google}"))

# En-tête principal avec compteurs
st.title("AvisExpress 🚀")

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Total SMS envoyés", total_envois)
col_m2.metric("Formule Actuelle", f"{plan_actuel}")

credits_restants = "Illimité" if plan_actuel in ["PRO", "EXPERT"] else max(0, LIMITE_CREDITS_STANDARD - total_envois)
col_m3.metric("Crédits restants", f"{credits_restants}" if plan_actuel in ["PRO", "EXPERT"] else f"{credits_restants} / {LIMITE_CREDITS_STANDARD}")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📲 Envoi de SMS", "💳 Abonnement & Offres", "📊 Historique & Export"])

# --- TAB 1 : ENVOI DE SMS ---
with tab1:
    st.header("📲 Envoyer une demande d'avis")
    
    if plan_actuel == "STANDARD" and total_envois >= LIMITE_CREDITS_STANDARD:
        st.error("⚠️ Vous avez atteint la limite de 5 SMS gratuits de la Formule STANDARD. Passez à la formule PRO ou EXPERT pour débloquer les SMS illimités.")
    else:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            pays = st.selectbox("Sélectionnez le pays du client :", [
                "Bénin (+229)", "Togo (+228)", "Côte d'Ivoire (+225)", 
                "Sénégal (+221)", "Cameroun (+237)", "France (+33)"
            ])
            indicatif = pays.split("(")[1].replace(")", "")
            num_saisi = st.text_input("Numéro de téléphone du client :", placeholder="ex: 0154341321")
            
        with col_c2:
            st.subheader("💬 Aperçu du SMS envoyé :")
            sms_final = msg_template.format(nom_commerce=nom_commerce, lien_google=lien_google)
            st.info(f'"{sms_final}"')

        if st.button("🚀 Envoyer la demande d'avis", type="primary"):
            if not num_saisi:
                st.warning("Veuillez saisir un numéro de téléphone.")
            else:
                num_complet = f"{indicatif}{num_saisi.strip()}"
                enregistrer_envoi(user["id"], num_complet)
                st.success(f"✅ Demande d'avis envoyée avec succès au {num_complet} !")
                st.rerun()

# --- TAB 2 : OFFRES & ABONNEMENTS ---
with tab2:
    st.header("💳 Formules d'abonnement")
    col1, col2 = st.columns(2)
    
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
            fedapay_pro_html = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="pay-btn-pro" style="background-color: #007bff; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                💳 Procéder au paiement (15 000 XOF)
            </button>
            <script>
                let widgetPro = FedaPay.init('#pay-btn-pro', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{ amount: 15000, description: "Abonnement PRO AvisExpress" }},
                    customer: {{ email: "{user['email']}" }},
                    onComplete: function(response) {{
                        if (response.reason === FedaPay.CHECKOUT_COMPLETED) {{
                            window.location.href = window.location.origin + "?id=" + response.transaction.id + "&plan=PRO";
                        }}
                    }}
                }});
            </script>
            '''
            st.components.v1.html(fedapay_pro_html, height=80)

    with col2:
        st.subheader("👑 Formule EXPERT")
        st.write("• SMS illimités")
        st.write("• Multi-boutiques & Multi-utilisateurs")
        st.write("• Support VIP 24/7 par téléphone")
        st.write("**Tarif : 30 000 XOF / mois**")
        
        if plan_actuel == "EXPERT":
            st.success("✅ Formule EXPERT actuellement active sur votre compte.")
        else:
            st.warning("⚠️ Vous n'avez pas encore procédé au paiement pour cette formule.")
            fedapay_expert_html = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="pay-btn-expert" style="background-color: #28a745; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                💳 Procéder au paiement (30 000 XOF)
            </button>
            <script>
                let widgetExpert = FedaPay.init('#pay-btn-expert', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{ amount: 30000, description: "Abonnement EXPERT AvisExpress" }},
                    customer: {{ email: "{user['email']}" }},
                    onComplete: function(response) {{
                        if (response.reason === FedaPay.CHECKOUT_COMPLETED) {{
                            window.location.href = window.location.origin + "?id=" + response.transaction.id + "&plan=EXPERT";
                        }}
                    }}
                }});
            </script>
            '''
            st.components.v1.html(fedapay_expert_html, height=80)

# --- TAB 3 : HISTORIQUE & EXPORT ---
with tab3:
    st.header("📊 Historique des envois")
    conn = get_db_connection()
    df_envois = pd.read_sql_query("SELECT telephone, date_envoi FROM envois WHERE user_id = ? ORDER BY date_envoi DESC", conn, params=(user["id"],))
    conn.close()
    
    if df_envois.empty:
        st.info("Aucun SMS n'a encore été envoyé.")
    else:
        st.dataframe(df_envois, use_container_width=True)
        csv = df_envois.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Télécharger l'historique (CSV)", data=csv, file_name="historique_envois_avisexpress.csv", mime="text/csv")

# --- BANDEAU DÉFILANT ANIMÉ (TICKER) ---
st.markdown("""
<style>
@keyframes ticker {
    0% { transform: translate3d(0, 0, 0); }
    100% { transform: translate3d(-50%, 0, 0); }
}
.ticker-wrap {
    width: 100%;
    overflow: hidden;
    background-color: #111827;
    padding: 10px 0;
    margin-top: 30px;
    border-radius: 8px;
}
.ticker {
    display: inline-block;
    white-space: nowrap;
    animation: ticker 25s linear infinite;
}
.ticker__item {
    display: inline-block;
    padding: 0 30px;
    font-size: 14px;
    color: #10B981;
    font-weight: bold;
}
</style>
<div class="ticker-wrap">
  <div class="ticker">
    <div class="ticker__item">🚀 AvisExpress: Boost your Google Reviews 3x faster!</div>
    <div class="ticker__item">🆓 STANDARD Plan: 5 Free SMS Trial</div>
    <div class="ticker__item">⭐ PRO Plan: Unlimited SMS & Analytics</div>
    <div class="ticker__item">👑 EXPERT Plan: Multi-store, A/B Testing & 24/7 VIP Support</div>
  </div>
</div>
""", unsafe_allow_html=True)
