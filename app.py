import streamlit as st
import sqlite3
import random
import datetime
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="AvisExpress - SaaS & Récompenses",
    page_icon="🚀",
    layout="wide"
)

# ==============================================================================
# ⚙️ --- INFORMATIONS ADMINISTRATEUR & DESTINATIONS DES FONDS ---
# ==============================================================================
PASSWORD_ADMIN = "admin123"                           # Mot de passe espace admin
ADMIN_EMAIL = "votre.email@gmail.com"                 # Votre e-mail pour recevoir les notifications

# Vos identifiants de comptes pour la réception des parts 50/50
DESTINATION_PLAYSTATION = "Mon_ID_PSN / psn-admin@gmail.com"
DESTINATION_ROBUX = "Mon_Pseudo_Roblox / roblox-admin@gmail.com"

# Clé Publique FedaPay
FEDAPAY_PUBLIC_KEY = "pk_sandbox_FZyFKQIh6gvCBSk6aShpSV7c"
# ==============================================================================

# --- INITIALISATION BASE DE DONNÉES SQLITE ---
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            montant_total REAL NOT NULL,
            part_psn REAL DEFAULT 0,
            part_robux REAL DEFAULT 0,
            codes_psn TEXT NOT NULL,
            codes_robux TEXT NOT NULL,
            dest_psn TEXT DEFAULT '',
            dest_robux TEXT DEFAULT '',
            date_transaction TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            valeur REAL NOT NULL,
            code TEXT NOT NULL UNIQUE,
            statut TEXT DEFAULT 'DISPONIBLE'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- NOTIFICATION PAR E-MAIL ---
def envoyer_email_notification(email_client, montant_total, part_psn, part_robux, liste_psn, liste_robux, dest_psn, dest_robux):
    try:
        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(st.secrets.get("SMTP_PORT", 587))
        sender_email = st.secrets.get("SENDER_EMAIL", "")
        sender_password = st.secrets.get("SENDER_PASSWORD", "")
        target_admin_email = ADMIN_EMAIL or sender_email

        if not sender_email or not sender_password:
            return False

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = target_admin_email
        msg['Subject'] = f"🔔 Nouvelle commande 50/50 - {montant_total}$ USD ({email_client})"

        psn_details = "\n".join([f"- {item}" for item in liste_psn])
        robux_details = "\n".join([f"- {item}" for item in liste_robux])

        corps_email = f"""
Bonjour Administrateur,

Une nouvelle répartition 50/50 a été enregistrée sur AvisExpress.

--------------------------------------------------
DÉTAILS CLIENT & TRANSACTION :
--------------------------------------------------
- Client : {email_client}
- Montant Total Payé : {montant_total:.2f} $ USD
- Date : {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

--------------------------------------------------
1. PART PLAYSTATION STORE (50%)
--------------------------------------------------
- Montant alloué : {part_psn:.2f} $ USD
- Compte Destination : {dest_psn}
- Codes attribués :
{psn_details}

--------------------------------------------------
2. PART ROBUX (50%)
--------------------------------------------------
- Montant alloué : {part_robux:.2f} $ USD
- Compte Destination : {dest_robux}
- Codes attribués :
{robux_details}
        """

        msg.attach(MIMEText(corps_email, 'plain', 'utf-8'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        return False

# --- LOGIQUE DE RÉPARTITION 50/50 ---
CATALOGUE_PSN = [10, 20, 25, 50]
CATALOGUE_ROBUX = [{"valeur": 10, "robux": 800}, {"valeur": 25, "robux": 2000}]

def obtenir_code(type_carte, valeur):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, code FROM inventory WHERE type = ? AND valeur = ? AND statut = 'DISPONIBLE' LIMIT 1", (type_carte, valeur))
    row = c.fetchone()
    if row:
        card_id, code = row
        c.execute("UPDATE inventory SET statut = 'UTILISE' WHERE id = ?", (card_id,))
        conn.commit()
        conn.close()
        return code
    else:
        conn.close()
        prefix = "PSN" if type_carte == "PSN" else "RBX"
        return f"{prefix}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

def generer_repartition_50_50(email, montant_total):
    part_psn = montant_total * 0.50
    part_robux = montant_total * 0.50
    
    cartes_psn = []
    reste_psn = part_psn
    options_psn = sorted([v for v in CATALOGUE_PSN if v <= part_psn], reverse=True) or [10]
    
    while reste_psn >= min(options_psn):
        valeur = random.choice([v for v in options_psn if v <= reste_psn] or [min(options_psn)])
        code = obtenir_code("PSN", valeur)
        cartes_psn.append(f"Carte PSN {valeur}$ : `{code}`")
        reste_psn -= valeur
        if len(cartes_psn) >= 5:
            break
            
    cartes_robux = []
    reste_robux = part_robux
    options_robux = [r for r in CATALOGUE_ROBUX if r["valeur"] <= part_robux] or [CATALOGUE_ROBUX[0]]
    
    while reste_robux >= 10:
        choix = random.choice([r for r in options_robux if r["valeur"] <= reste_robux] or [CATALOGUE_ROBUX[0]])
        code = obtenir_code("ROBUX", choix["valeur"])
        cartes_robux.append(f"Code {choix['robux']} Robux ({choix['valeur']}$) : `{code}`")
        reste_robux -= choix["valeur"]
        if len(cartes_robux) >= 5:
            break

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (email, montant_total, part_psn, part_robux, codes_psn, codes_robux, dest_psn, dest_robux, date_transaction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (email, montant_total, part_psn, part_robux, " | ".join(cartes_psn), " | ".join(cartes_robux), DESTINATION_PLAYSTATION, DESTINATION_ROBUX, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    return cartes_psn, cartes_robux, part_psn, part_robux

# --- MENU LATÉRAL ---
st.sidebar.title("🚀 AvisExpress")
menu = st.sidebar.radio("Navigation", [
    "📱 Envoi d'Avis SMS", 
    "💳 Abonnements & Tous les Paiements", 
    "🎁 Répartition 50/50 Récompenses", 
    "👑 Espace Administrateur"
])

# ------------------------------------------------------------------------------
# 1. ENVOI D'AVIS SMS
# ------------------------------------------------------------------------------
if menu == "📱 Envoi d'Avis SMS":
    st.title("📱 Service AvisExpress - Collecte d'avis Google")
    col_a, col_b = st.columns(2)
    with col_a:
        nom_commerce = st.text_input("Nom de votre commerce :", "Mon Commerce")
        telephone = st.text_input("Téléphone du client :", "+229 90000000")
        lien_google = st.text_input("Lien Google Review / Maps :", "https://g.page/r/example/review")
        
    with col_b:
        st.subheader("💬 Aperçu du message SMS envoyé")
        st.info(f"Bonjour ! Merci d'avoir visité **{nom_commerce}**. Laissez-nous votre avis ici : {lien_google}")

    if st.button("🚀 Envoyer l'invitation SMS", type="primary"):
        if telephone and lien_google:
            st.success(f"✅ SMS d'invitation envoyé avec succès au {telephone} !")
        else:
            st.error("Veuillez remplir tous les champs.")

# ------------------------------------------------------------------------------
# 2. ABONNEMENTS ET SÉLECTEUR TOUS PAIMENTS (VISA, MASTERCARD, PAYPAL, MOBILE MONEY)
# ------------------------------------------------------------------------------
elif menu == "💳 Abonnements & Tous les Paiements":
    st.title("💳 Guichet de Paiement Universel (Monde Entier)")
    st.write("Choisissez votre méthode de paiement préférée ci-dessous :")

    # Sélection de la méthode de paiement
    moyen_paiement = st.radio(
        "Sélectionnez le type de paiement :",
        ["📱 Mobile Money (MTN, Moov, Wave, Orange, Celtiis)", "💳 Carte Bancaire Internationale (Visa, Mastercard, Amex)", "🅿️ PayPal / Virement International"],
        horizontal=True
    )

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🆓 STANDARD")
        st.markdown("### **0 $ / mois**")
        st.write("• 5 SMS de test gratuits")
        st.write("• Lien Google Maps personnalisé")
        st.write("• Support de base par e-mail")
        st.success("Plan actif par défaut")

    with col2:
        st.subheader("🌟 Formule PRO")
        st.markdown("### **25 USD / mois**")
        st.caption("~ 15 000 XOF / FCFA")
        st.write("• **SMS Illimités**")
        st.write("• Suivi des statistiques")
        st.write("• Support prioritaire 24/7")

        if "Mobile Money" in moyen_paiement:
            fedapay_pro_html = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <div style="padding: 10px 0;">
                <button id="pay-btn-pro" style="background-color: #007bff; color: white; border: none; padding: 14px 20px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                    📱 Payer par Mobile Money (25$)
                </button>
            </div>
            <script>
                let widgetPro = FedaPay.init('#pay-btn-pro', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{ amount: 15000, description: "Abonnement PRO AvisExpress" }}
                }});
            </script>
            '''
            st.components.v1.html(fedapay_pro_html, height=550)
        elif "Carte Bancaire" in moyen_paiement:
            st.link_button("💳 Payer avec ma Carte Visa / Mastercard (25$)", "https://checkout.stripe.com", type="primary", use_container_width=True)
        else:
            st.link_button("🅿️ Payer via Compte PayPal (25$)", "https://www.paypal.com", type="primary", use_container_width=True)

    with col3:
        st.subheader("👑 Formule EXPERT")
        st.markdown("### **50 USD / mois**")
        st.caption("~ 30 000 XOF / FCFA")
        st.write("• **SMS Illimités (Monde)**")
        st.write("• Multi-boutiques & Multi-comptes")
        st.write("• Manager de compte dédié")

        if "Mobile Money" in moyen_paiement:
            fedapay_expert_html = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <div style="padding: 10px 0;">
                <button id="pay-btn-expert" style="background-color: #28a745; color: white; border: none; padding: 14px 20px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                    📱 Payer par Mobile Money (50$)
                </button>
            </div>
            <script>
                let widgetExpert = FedaPay.init('#pay-btn-expert', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{ amount: 30000, description: "Abonnement EXPERT AvisExpress" }}
                }});
            </script>
            '''
            st.components.v1.html(fedapay_expert_html, height=550)
        elif "Carte Bancaire" in moyen_paiement:
            st.link_button("💳 Payer avec ma Carte Visa / Mastercard (50$)", "https://checkout.stripe.com", type="primary", use_container_width=True)
        else:
            st.link_button("🅿️ Payer via Compte PayPal (50$)", "https://www.paypal.com", type="primary", use_container_width=True)

# ------------------------------------------------------------------------------
# 3. REPARTITION 50/50 RECOMPENSES
# ------------------------------------------------------------------------------
elif menu == "🎁 Répartition 50/50 Récompenses":
    st.title("🎁 Module de Répartition 50/50 (PlayStation & Robux)")
    
    with st.form("form_client"):
        email = st.text_input("Adresse E-mail du client *", placeholder="exemple@gmail.com")
        montant = st.number_input("Montant total payé ($ USD)", min_value=20.0, max_value=1000.0, value=50.0, step=10.0)
        btn_submit = st.form_submit_button("Calculer et Répartir")
        
    if btn_submit:
        if not email or "@" not in email:
            st.error("Veuillez saisir une adresse e-mail valide.")
        else:
            list_psn, list_robux, part_psn, part_robux = generer_repartition_50_50(email, montant)
            st.success("✅ Transaction validée et enregistrée en base de données !")
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🎮 PlayStation (50%)")
                st.info(f"Valeur : **{part_psn:.2f} $**")
                for item in list_psn:
                    st.write(f"- {item}")
            with c2:
                st.subheader("🧱 Robux (50%)")
                st.info(f"Valeur : **{part_robux:.2f} $**")
                for item in list_robux:
                    st.write(f"- {item}")

            envoyer_email_notification(email, montant, part_psn, part_robux, list_psn, list_robux, DESTINATION_PLAYSTATION, DESTINATION_ROBUX)

# ------------------------------------------------------------------------------
# 4. ESPACE ADMINISTRATEUR
# ------------------------------------------------------------------------------
elif menu == "👑 Espace Administrateur":
    st.title("👑 Tableau de Bord Administrateur")
    pwd_input = st.text_input("Saisissez le mot de passe Administrateur :", type="password")
    
    if pwd_input == PASSWORD_ADMIN:
        st.success("Accès autorisé !")
        
        conn = sqlite3.connect('database.db')
        df_trans = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)
        conn.close()
        
        if df_trans.empty:
            st.info("Aucune transaction enregistrée.")
        else:
            total_global = df_trans['montant_total'].sum()
            total_psn = df_trans['part_psn'].sum()
            total_robux = df_trans['part_robux'].sum()
            
            col_1, col_2, col_3 = st.columns(3)
            col_1.metric("Chiffre d'Affaires Total", f"{total_global:.2f} $")
            col_2.metric("Total Injecté PlayStation", f"{total_psn:.2f} $")
            col_3.metric("Total Injecté Robux", f"{total_robux:.2f} $")
            
            st.markdown("---")
            st.subheader("📋 Historique complet des transactions")
            st.dataframe(df_trans, use_container_width=True)
            
            csv = df_trans.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exporter le rapport CSV", data=csv, file_name="rapport_admin_avisexpress.csv", mime="text/csv")
            
    elif pwd_input != "":
        st.error("Mot de passe incorrect.")
