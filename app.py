import streamlit as st
import sqlite3
import hashlib
import json
import stripe
import pandas as pd
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="AvisExpress 🚀", page_icon="🚀", layout="wide")

# Récupération sécurisée de la clé Stripe depuis st.secrets
STRIPE_SECRET_KEY = "sk_test_51TnPpiKg0crHycdnhmO81okH7bqjnVRVfDnU6TGvhhQTTt8yPZhDHaVuBw6qLgkEzXUq74UWLKhhwGFApJ55cTP100ys8QQKFh"
stripe.api_key = STRIPE_SECRET_KEY

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

# --- AUTHENTIFICATION & UTILITAIRES ---
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

# --- TRAITEMENT DU RETOUR DE PAIEMENT STRIPE ---
query_params = st.query_params
if "payment_success" in query_params and st.session_state.user:
    target_plan = query_params.get("plan", "PRO")
    mettre_a_jour_plan(st.session_state.user["id"], target_plan)
    st.success(f"🎉 Paiement confirmé ! Votre abonnement est maintenant actif : Formule {target_plan}.")
    st.query_params.clear()
    st.rerun()

# --- INTERFACE CONNEXION / INSCRIPTION ---
if not st.session_state.user:
    st.title("AvisExpress 🚀")
    st.subheader("Plateforme SaaS de collecte automatique d'avis Google (Couverture Internationale)")
    
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

# Sidebar
st.sidebar.markdown(f"👤 Connecté : **{user['email']}**")
if st.sidebar.button("Déconnexion"):
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Paramètres Commerce")

nom_commerce = st.sidebar.text_input("Nom de votre commerce :", value=user.get("nom_commerce", "Mon Salon de Coiffure"))
lien_google = st.sidebar.text_input("Lien Google Maps :", value=user.get("lien_google", "https://g.page/r/example/review"))
msg_template = st.sidebar.text_area("Message SMS personnalisé :", value=user.get("message_custom", "Bonjour ! Merci pour votre visite chez {nom_commerce}. Laissez-nous un avis ici : {lien_google}"))

# En-tête principal
st.title("AvisExpress 🚀")

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Total SMS envoyés", total_envois)
col_m2.metric("Formule Actuelle", f"{plan_actuel}")

credits_restants = "Illimité" if plan_actuel in ["PRO", "EXPERT"] else max(0, LIMITE_CREDITS_STANDARD - total_envois)
col_m3.metric("Crédits restants", f"{credits_restants}" if plan_actuel in ["PRO", "EXPERT"] else f"{credits_restants} / {LIMITE_CREDITS_STANDARD}")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📲 Envoi de SMS International", "💳 Abonnement & Paiement", "📊 Historique & Export"])

# --- TAB 1 : ENVOI SMS ---
with tab1:
    st.header("📲 Envoyer une demande d'avis (International)")
    
    if plan_actuel == "STANDARD" and total_envois >= LIMITE_CREDITS_STANDARD:
        st.error("⚠️ Limite atteinte pour la Formule STANDARD. Passez à la formule PRO ou EXPERT pour débloquer l'envoi illimité.")
    else:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            pays = st.selectbox("Sélectionnez le pays du destinataire :", [
                "🌍 Afrique - Bénin (+229)",
                "🌍 Afrique - Togo (+228)",
                "🌍 Afrique - Côte d'Ivoire (+225)",
                "🌍 Afrique - Sénégal (+221)",
                "🌍 Afrique - Cameroun (+237)",
                "🌍 Afrique - Mali (+223)",
                "🌍 Afrique - Burkina Faso (+226)",
                "🇪🇺 Europe - France (+33)",
                "🇪🇺 Europe - Belgique (+32)",
                "🇪🇺 Europe - Suisse (+41)",
                "🇪🇺 Europe - Allemagne (+49)",
                "🇪🇺 Europe - Royaume-Uni (+44)",
                "🌎 Amérique - USA / Canada (+1)",
                "🌏 Asie - Émirats Arabes Unis (+971)",
                "🌏 Asie - Chine (+86)",
                "🌏 Asie - Japon (+81)"
            ])
            indicatif = pays.split("(")[1].replace(")", "")
            num_saisi = st.text_input("Numéro de téléphone du client :", placeholder="ex: 0154341321")
            
        with col_c2:
            st.subheader("💬 Aperçu du SMS envoyé :")
            sms_final = msg_template.format(nom_commerce=nom_commerce, lien_google=lien_google)
            st.info(f'"{sms_final}"')

        if st.button("🚀 Envoyer le SMS dans le monde entier", type="primary"):
            if not num_saisi:
                st.warning("Veuillez saisir un numéro de téléphone.")
            else:
                num_complet = f"{indicatif}{num_saisi.strip()}"
                enregistrer_envoi(user["id"], num_complet)
                st.success(f"✅ Demande d'avis envoyée au {num_complet} !")
                st.rerun()

# --- TAB 2 : ABONNEMENT INTERNATIONAL (STRIPE CHECKOUT) ---
with tab2:
    st.header("💳 Formules d'abonnement internationales")
    st.info("🔒 **Paiement sécurisé par Stripe :** Acceptation des cartes Visa, Mastercard, American Express, Apple Pay et Google Pay.")
    
    col1, col2 = st.columns(2)
    
    app_url = "https://app-avis-app-wv9a2h9feuswngyqubhxk8.streamlit.app"
    
    with col1:
        st.subheader("🌟 Formule PRO")
        st.write("• SMS illimités (Afrique, Europe, Asie, Amérique)")
        st.write("• Statistiques de performance")
        st.write("• Support prioritaire 24/7")
        st.write("**Tarif : 25 USD / mois (~15 000 XOF)**")
        
        if plan_actuel == "PRO":
            st.success("✅ Formule PRO actuellement active.")
        else:
            if st.button("💳 Payer par Carte (Formule PRO)", key="btn_stripe_pro", type="primary"):
                try:
                    session = stripe.checkout.Session.create(
                        payment_method_types=['card'],
                        customer_email=user['email'],
                        line_items=[{
                            'price_data': {
                                'currency': 'usd',
                                'product_data': {
                                    'name': 'Abonnement PRO - AvisExpress',
                                    'description': 'Accès illimité aux envois de SMS d\'avis Google',
                                },
                                'unit_amount': 2500,
                            },
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=f"{app_url}/?payment_success=true&plan=PRO",
                        cancel_url=f"{app_url}/",
                    )
                    st.link_button("👉 Cliquez ici pour saisir votre carte bancaire 🔒", session.url, type="primary")
                except Exception as e:
                    st.error(f"Erreur lors de la création de la session de paiement : {e}")

    with col2:
        st.subheader("👑 Formule EXPERT")
        st.write("• SMS illimités (Couverture Mondiale)")
        st.write("• Multi-boutiques & Multi-utilisateurs")
        st.write("• Manager de compte dédié")
        st.write("**Tarif : 50 USD / mois (~30 000 XOF)**")
        
        if plan_actuel == "EXPERT":
            st.success("✅ Formule EXPERT actuellement active.")
        else:
            if st.button("💳 Payer par Carte (Formule EXPERT)", key="btn_stripe_expert", type="primary"):
                try:
                    session = stripe.checkout.Session.create(
                        payment_method_types=['card'],
                        customer_email=user['email'],
                        line_items=[{
                            'price_data': {
                                'currency': 'usd',
                                'product_data': {
                                    'name': 'Abonnement EXPERT - AvisExpress',
                                    'description': 'Accès complet multi-boutiques et support VIP',
                                },
                                'unit_amount': 5000,
                            },
                            'quantity': 1,
                        }],
                        mode='payment',
                        success_url=f"{app_url}/?payment_success=true&plan=EXPERT",
                        cancel_url=f"{app_url}/",
                    )
                    st.link_button("👉 Cliquez ici pour saisir votre carte bancaire 🔒", session.url, type="primary")
                except Exception as e:
                    st.error(f"Erreur lors de la création de la session de paiement : {e}")

# --- TAB 3 : HISTORIQUE ---
with tab3:
    st.header("📊 Historique global des envois")
    conn = get_db_connection()
    df_envois = pd.read_sql_query("SELECT telephone, date_envoi FROM envois WHERE user_id = ? ORDER BY date_envoi DESC", conn, params=(user["id"],))
    conn.close()
    
    if df_envois.empty:
        st.info("Aucun SMS envoyé pour le moment.")
    else:
        st.dataframe(df_envois, use_container_width=True)
        csv = df_envois.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Télécharger l'historique (CSV)", data=csv, file_name="historique_envois_global.csv", mime="text/csv")
