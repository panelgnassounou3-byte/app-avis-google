import streamlit as st
import streamlit.components.v1 as components
import phonenumbers
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from babel import Locale
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd

# Configuration de la page
st.set_page_config(page_title="AvisExpress", page_icon="🚀", layout="centered")

locale_fr = Locale('fr')

# --- CONFIGURATION DES TARIFS ET CLÉ API ---
QUOTA_STANDARD = 5
TARIFS = {
    "STANDARD": {"EUR": 0, "XOF": 0},
    "PRO": {"EUR": 15, "XOF": 10000},
    "EXPERT": {"EUR": 35, "XOF": 23000}
}

FEDAPAY_PUBLIC_KEY = "pk_sandbox_FZyFKQIh6gvCBSk6aShpSV7c"
NOM_BDD = "avisexpress_v2.db"

# --- FONCTIONS DE HACHAGE DES MOTS DE PASSE ---
def mef_hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def mef_verify_password(password, hashed_password):
    return mef_hash_password(password) == hashed_password

# --- BASE DE DONNÉES SQLITE AVEC GESTION MULTI-UTILISATEURS ---
def init_db():
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    # Table des utilisateurs
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, plan TEXT DEFAULT 'STANDARD')''')
    
    # Table des envois liée à l'utilisateur via user_id
    c.execute('''CREATE TABLE IF NOT EXISTS envois 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, telephone TEXT, message TEXT)''')
    conn.commit()
    conn.close()

def inscrire_utilisateur(email, password):
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    try:
        hashed_pwd = mef_hash_password(password)
        c.execute("INSERT INTO utilisateurs (email, password, plan) VALUES (?, ?, 'STANDARD')", (email, hashed_pwd))
        conn.commit()
        conn.close()
        return True, "Compte créé avec succès ! Vous pouvez maintenant vous connecter."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Cet e-mail est déjà utilisé."

def connecter_utilisateur(email, password):
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    hashed_pwd = mef_hash_password(password)
    c.execute("SELECT id, email, plan FROM utilisateurs WHERE email = ? AND password = ?", (email, hashed_pwd))
    user = c.fetchone()
    conn.close()
    return user

def enregistrer_envoi(user_id, telephone, message):
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    date_heure = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO envois (user_id, date, telephone, message) VALUES (?, ?, ?, ?)", (user_id, date_heure, telephone, message))
    conn.commit()
    conn.close()

def lire_historique(user_id):
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    c.execute("SELECT date, telephone, message FROM envois WHERE user_id = ? ORDER BY id DESC", (user_id,))
    donnees = c.fetchall()
    conn.close()
    return donnees

def tout_exporter(user_id):
    conn = sqlite3.connect(NOM_BDD)
    df = pd.read_sql_query("SELECT date AS 'Date et Heure', telephone AS 'Numéro Client', message AS 'Message SMS' FROM envois WHERE user_id = ? ORDER BY id DESC", conn, params=(user_id,))
    conn.close()
    return df.to_csv(index=False).encode('utf-8')

def obtenir_statistiques(user_id):
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM envois WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    
    c.execute("SELECT plan FROM utilisateurs WHERE id = ?", (user_id,))
    res = c.fetchone()
    plan_actuel = res[0] if res else "STANDARD"
    conn.close()
    return total, plan_actuel

def changer_plan(user_id, nouveau_plan):
    conn = sqlite3.connect(NOM_BDD)
    c = conn.cursor()
    c.execute("UPDATE utilisateurs SET plan = ? WHERE id = ?", (nouveau_plan, user_id))
    conn.commit()
    conn.close()

init_db()

# --- GESTION DE LA SESSION DE CONNEXION ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# ==================== PAGE DE CONNEXION / INSCRIPTION ====================
if st.session_state['user'] is None:
    st.title("AvisExpress 🚀")
    st.markdown("##### Connectez-vous à votre espace marchand")

    onglet_connexion, onglet_inscription = st.tabs(["🔑 Se connecter", "📝 Créer un compte"])

    with onglet_connexion:
        email_login = st.text_input("E-mail :", key="login_email")
        password_login = st.text_input("Mot de passe :", type="password", key="login_password")
        
        if st.button("Se connecter", type="primary"):
            if email_login and password_login:
                user = connecter_utilisateur(email_login, password_login)
                if user:
                    st.session_state['user'] = {"id": user[0], "email": user[1], "plan": user[2]}
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("E-mail ou mot de passe incorrect.")
            else:
                st.warning("Veuillez remplir tous les champs.")

    with onglet_inscription:
        email_signup = st.text_input("E-mail :", key="signup_email")
        password_signup = st.text_input("Mot de passe :", type="password", key="signup_password")
        
        if st.button("Créer mon compte"):
            if email_signup and password_signup:
                succes, msg = inscrire_utilisateur(email_signup, password_signup)
                if succes:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Veuillez remplir tous les champs.")

# ==================== ESPACE PRIVE DU COMMERÇANT ====================
else:
    user_id = st.session_state['user']['id']
    user_email = st.session_state['user']['email']

    # --- BARRE LATÉRALE ---
    with st.sidebar:
        st.write(f"👤 Connecté : **{user_email}**")
        if st.button("🚪 Déconnexion"):
            st.session_state['user'] = None
            st.rerun()
            
        st.write("---")
        st.header("⚙️ Paramètres Commerce")
        nom_commerce = st.text_input("Nom de votre commerce :", value="Mon Salon de Coiffure")
        lien_google = st.text_input("Lien Google Maps :", value="https://g.page/r/example/review")
        
        message_template = st.text_area(
            "Message SMS personnalisé :",
            value=f"Bonjour ! Merci pour votre visite chez {nom_commerce}. Laissez-nous un avis ici : {lien_google}",
            height=140
        )

    # --- EN-TÊTE ET MÉTRIQUES PRIVÉES ---
    st.title("AvisExpress 🚀")
    total_envois, plan_actuel = obtenir_statistiques(user_id)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total SMS envoyés", total_envois)

    if plan_actuel in ["PRO", "EXPERT"]:
        col2.metric("Formule Actuelle", f"⭐ {plan_actuel}")
        col3.metric("Crédits SMS", "∞ Illimités")
    else:
        credits_restants = max(0, QUOTA_STANDARD - total_envois)
        col2.metric("Formule Actuelle", "🆓 STANDARD")
        col3.metric("Crédits restants", f"{credits_restants} / {QUOTA_STANDARD}")

    st.write("---")

    # --- ORGANISATION EN 3 ONGLETS PRIVÉS ---
    tab_sms, tab_abonnement, tab_historique = st.tabs(["📲 Envoi de SMS", "💳 Abonnement & Offres", "📊 Historique & Export"])

    # ==================== ONGLET 1 : ENVOI DE SMS ====================
    with tab_sms:
        st.subheader("📲 Envoyer une demande d'avis")

        options_pays = []
        codes_vers_pays = {}

        for code_indicatif, liste_iso in COUNTRY_CODE_TO_REGION_CODE.items():
            for iso in liste_iso:
                nom_pays_fr = locale_fr.territories.get(iso.upper())
                if nom_pays_fr:
                    label = f"{nom_pays_fr} (+{code_indicatif})"
                    options_pays.append(label)
                    codes_vers_pays[label] = f"+{code_indicatif}"

        options_pays = sorted(list(set(options_pays)))

        index_defaut = 0
        for idx, item in enumerate(options_pays):
            if "Bénin" in item or "Côte d'Ivoire" in item:
                index_defaut = idx
                break

        pays_selectionne = st.selectbox("Sélectionnez le pays du client :", options_pays, index=index_defaut)
        indicatif = codes_vers_pays[pays_selectionne]
        numero_local = st.text_input("Numéro de téléphone du client :", placeholder="ex: 0154341321")

        numero_complet = f"{indicatif}{numero_local.strip()}"

        st.info(f"💬 **Aperçu du SMS envoyé :**\n\n\"{message_template}\"")

        quota_depasse = (plan_actuel == "STANDARD") and (total_envois >= QUOTA_STANDARD)

        if quota_depasse:
            st.error(f"🚨 **Limite atteinte !** Vous avez consommé vos {QUOTA_STANDARD} SMS gratuits.")
            st.info("👉 Allez dans l'onglet **💳 Abonnement & Offres** pour choisir la formule PRO ou EXPERT.")
            st.button("🚀 Envoyer la demande d'avis", disabled=True)
        else:
            if st.button("🚀 Envoyer la demande d'avis", type="primary"):
                if not numero_local:
                    st.warning("Veuillez entrer un numéro de téléphone.")
                else:
                    try:
                        parsed_number = phonenumbers.parse(numero_complet, None)
                        if phonenumbers.is_valid_number(parsed_number):
                            numero_formate = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                            enregistrer_envoi(user_id, numero_formate, message_template)
                            st.success(f"SMS enregistré avec succès pour le {numero_formate} !")
                            st.rerun()
                        else:
                            st.error(f"Le numéro {numero_complet} n'est pas valide pour ce pays.")
                    except Exception:
                        st.error("Format de numéro invalide. Vérifiez la saisie.")

    # ==================== ONGLET 2 : ABONNEMENT & OFFRES ====================
    with tab_abonnement:
        st.subheader("💳 Choix de la Formule")

        choix_plan = st.radio(
            "Sélectionnez une formule :",
            options=["STANDARD (0 €/mois)", f"PRO ({TARIFS['PRO']['EUR']} €/mois)", f"EXPERT ({TARIFS['EXPERT']['EUR']} €/mois)"],
            index=0 if plan_actuel == "STANDARD" else (1 if plan_actuel == "PRO" else 2)
        )
        
        plan_selectionne = choix_plan.split()[0]

        st.markdown("---")
        st.subheader("📋 Avantages inclus :")
        if plan_selectionne == "STANDARD":
            st.write("• **5 SMS de test offerts**")
            st.write("• Personnalisation du message")
            st.write("• Export CSV des données")
        elif plan_selectionne == "PRO":
            st.write("• **SMS illimités**")
            st.write("• **Statistiques de performance**")
            st.write("• Support prioritaire par e-mail")
        else:
            st.write("• **SMS illimités**")
            st.write("• **Multi-commerces & Multi-liens**")
            st.write("• **Modèles A/B Testing**")
            st.write("• **Support dédié 7j/7**")

        st.markdown("---")
        if plan_selectionne != "STANDARD" and plan_selectionne != plan_actuel:
            montant_xof = TARIFS[plan_selectionne]["XOF"]
            montant_eur = TARIFS[plan_selectionne]["EUR"]
            
            st.subheader("🔒 Procéder au Paiement")
            st.write(f"Montant : **{montant_eur} €** (~{montant_xof:,} FCFA)".replace(",", " "))

            fedapay_checkout_code = f"""
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="pay-btn" style="
                background-color: #28a745; 
                color: white; 
                padding: 12px 24px; 
                border: none; 
                border-radius: 6px; 
                font-size: 16px; 
                font-weight: bold;
                cursor: pointer;
                width: 100%;">
                💳 Payer avec Mobile Money / CB
            </button>
            <script>
                let widget = FedaPay.init('#pay-btn', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{
                        amount: {montant_xof},
                        description: 'Abonnement AvisExpress {plan_selectionne}'
                    }},
                    customer: {{
                        email: '{user_email}',
                        lastname: '{nom_commerce}'
                    }}
                }});
            </script>
            """
            components.html(fedapay_checkout_code, height=70)

            if st.button(f"✅ Valider l'activation (Test {plan_selectionne})"):
                changer_plan(user_id, plan_selectionne)
                st.session_state['user']['plan'] = plan_selectionne
                st.success(f"Abonnement {plan_selectionne} activé avec succès !")
                st.rerun()

        elif plan_selectionne == plan_actuel and plan_actuel != "STANDARD":
            st.success(f"✅ Formule {plan_actuel} actuellement active sur votre compte.")
            if st.button("Basculer au plan Gratuit (Test)"):
                changer_plan(user_id, "STANDARD")
                st.session_state['user']['plan'] = "STANDARD"
                st.rerun()

    # ==================== ONGLET 3 : HISTORIQUE & EXPORT ====================
    with tab_historique:
        st.subheader("📊 Historique des envois")
        historique = lire_historique(user_id)

        if historique:
            if st.button("📥 Télécharger mes données (.CSV)"):
                csv_data = tout_exporter(user_id)
                st.download_button(
                    label="Cliquez pour lancer le téléchargement",
                    data=csv_data,
                    file_name=f"avisexpress_historique_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            st.write("---")
            for date_envoi, tel, msg in historique:
                with st.expander(f"🕒 {date_envoi} - Client : {tel}"):
                    st.write(f"**Message :** {msg}")
        else:
            st.info("Aucune demande enregistrée pour votre compte.")

    # --- BANDEAU DÉFILANT EN BAS DE PAGE ---
    st.write("---")

    ticker_html = """
    <style>
    .ticker-wrap {
      width: 100%;
      overflow: hidden;
      background-color: #1e1e1e;
      padding: 12px 0;
      border-radius: 8px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }

    .ticker {
      display: inline-block;
      white-space: nowrap;
      padding-left: 100%;
      animation: ticker 22s linear infinite;
    }

    .ticker__item {
      display: inline-block;
      padding: 0 2rem;
      font-size: 1.05rem;
      color: #00e676;
      font-weight: 600;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    @keyframes ticker {
      0% { transform: translate3d(0, 0, 0); }
      100% { transform: translate3d(-100%, 0, 0); }
    }
    </style>

    <div class="ticker-wrap">
      <div class="ticker">
        <div class="ticker__item">🚀 AvisExpress: Boost your Google Reviews 3x faster!</div>
        <div class="ticker__item">🆓 STANDARD Plan: 0€ / Free Trial (5 SMS)</div>
        <div class="ticker__item">⭐ PRO Plan: 15€ / Month - Unlimited SMS & Analytics</div>
        <div class="ticker__item">👑 EXPERT Plan: 35€ / Month - Multi-store, A/B Testing & 24/7 Support</div>
        <div class="ticker__item">💳 Secure Mobile Money & Card Payments via FedaPay</div>
      </div>
    </div>
    """

    components.html(ticker_html, height=70)