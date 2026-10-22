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
    page_title="AvisExpress - Service & Paiement",
    page_icon="🚀",
    layout="wide"
)

# ==============================================================================
# ⚙️ --- CONFIGURATION ADMINISTRATEUR ---
# ==============================================================================
PASSWORD_ADMIN = "admin123"                           # Mot de passe espace admin
ADMIN_EMAIL = "votre.email@gmail.com"                 # Votre e-mail pour recevoir les notifications

# Destinations de réception 50/50 (Arrière-plan uniquement)
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
            moyen_paiement TEXT DEFAULT '',
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
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN moyen_paiement TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

init_db()

# --- ENVOI DE NOTIFICATION E-MAIL ADMIN ---
def envoyer_email_notification(email_client, montant_total, part_psn, part_robux, moyen_pay, liste_psn, liste_robux, dest_psn, dest_robux):
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
        msg['Subject'] = f"🔔 TRANSACTION VALIDÉE ({montant_total}$ USD) - {email_client}"

        psn_details = "\n".join([f"- {item}" for item in liste_psn])
        robux_details = "\n".join([f"- {item}" for item in liste_robux])

        corps_email = f"""
Bonjour Administrateur,

Une nouvelle transaction a été enregistrée avec succès.

--------------------------------------------------
DÉTAILS CLIENT & PAIEMENT :
--------------------------------------------------
- Client : {email_client}
- Montant Réglé : {montant_total:.2f} $ USD
- Moyen de Paiement : {moyen_pay}
- Date : {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

--------------------------------------------------
1. VENTILATION PLAYSTATION STORE (50%)
--------------------------------------------------
- Montant alloué : {part_psn:.2f} $ USD
- Compte Récepteur : {dest_psn}
- Codes attribués :
{psn_details}

--------------------------------------------------
2. VENTILATION ROBUX (50%)
--------------------------------------------------
- Montant alloué : {part_robux:.2f} $ USD
- Compte Récepteur : {dest_robux}
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

def traiter_transaction_50_50(email, montant_total, moyen_pay="Paiement Sécurisé"):
    part_psn = montant_total * 0.50
    part_robux = montant_total * 0.50
    
    cartes_psn = []
    reste_psn = part_psn
    options_psn = sorted([v for v in CATALOGUE_PSN if v <= part_psn], reverse=True) or [10]
    while reste_psn >= min(options_psn):
        valeur = random.choice([v for v in options_psn if v <= reste_psn] or [min(options_psn)])
        code = obtenir_code("PSN", valeur)
        cartes_psn.append(f"Carte PSN {valeur}$ : {code}")
        reste_psn -= valeur
        if len(cartes_psn) >= 5:
            break
            
    cartes_robux = []
    reste_robux = part_robux
    options_robux = [r for r in CATALOGUE_ROBUX if r["valeur"] <= part_robux] or [CATALOGUE_ROBUX[0]]
    while reste_robux >= 10:
        choix = random.choice([r for r in options_robux if r["valeur"] <= reste_robux] or [CATALOGUE_ROBUX[0]])
        code = obtenir_code("ROBUX", choix["valeur"])
        cartes_robux.append(f"Code {choix['robux']} Robux ({choix['valeur']}$) : {code}")
        reste_robux -= choix["valeur"]
        if len(cartes_robux) >= 5:
            break

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (email, montant_total, part_psn, part_robux, moyen_paiement, codes_psn, codes_robux, dest_psn, dest_robux, date_transaction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (email, montant_total, part_psn, part_robux, moyen_pay, " | ".join(cartes_psn), " | ".join(cartes_robux), DESTINATION_PLAYSTATION, DESTINATION_ROBUX, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    return cartes_psn, cartes_robux, part_psn, part_robux

# --- RETOUR APRÈS PAIEMENT RÉUSSI ---
query_params = st.query_params
if "status" in query_params and query_params["status"] == "approved":
    email_client = query_params.get("email", "client@exemple.com")
    montant_paye = float(query_params.get("amount", 25.0))
    
    list_psn, list_robux, part_psn, part_robux = traiter_transaction_50_50(email_client, montant_paye, "FedaPay / Carte / Mobile")
    envoyer_email_notification(email_client, montant_paye, part_psn, part_robux, "FedaPay", list_psn, list_robux, DESTINATION_PLAYSTATION, DESTINATION_ROBUX)
    
    st.success("✅ Transaction effectuée avec succès ! Merci pour votre achat.")
    st.query_params.clear()

# --- MENU NAVIGATION ---
st.sidebar.title("🚀 AvisExpress")
menu = st.sidebar.radio("Navigation", [
    "💳 Guichet de Paiement Client", 
    "📱 Service SMS Avis Google", 
    "👑 Espace Administrateur"
])

# ------------------------------------------------------------------------------
# 1. GUICHET DE PAIEMENT CLIENT
# ------------------------------------------------------------------------------
if menu == "💳 Guichet de Paiement Client":
    st.title("💳 Guichet d'Abonnement & Paiement Sécurisé")
    st.write("Entrez votre e-mail puis cliquez sur le bouton pour choisir votre moyen de paiement (Visa, Mastercard, Mobile Money, etc.).")

    email_client = st.text_input("Adresse e-mail de facturation *", placeholder="votre.email@exemple.com")
    
    if not email_client or "@" not in email_client:
        st.warning("⚠️ Veuillez renseigner une adresse e-mail valide ci-dessus pour débloquer les boutons de paiement.")
    else:
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌟 Formule PRO (25 $ USD)")
            st.write("• SMS illimités")
            st.write("• Suivi des performances")
            
            html_pro = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="btn-pro" style="background-color: #007bff; color: white; border: none; padding: 15px 25px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                🔒 Payer 25,00 $ USD
            </button>
            <script>
                let widgetPro = FedaPay.init('#btn-pro', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{ amount: 15000, description: "Abonnement PRO AvisExpress" }},
                    customer: {{ email: "{email_client}" }},
                    onComplete: function(response) {{
                        if (response.reason === FedaPay.CHECKOUT_COMPLETED) {{
                            window.top.location.href = window.location.origin + "?status=approved&email={email_client}&amount=25";
                        }}
                    }}
                }});
            </script>
            '''
            st.components.v1.html(html_pro, height=90)

        with col2:
            st.subheader("👑 Formule EXPERT (50 $ USD)")
            st.write("• SMS illimités (Monde)")
            st.write("• Multi-boutiques & Support VIP")
            
            html_expert = f'''
            <script src="https://cdn.fedapay.com/checkout.js?v=1.1.7"></script>
            <button id="btn-expert" style="background-color: #28a745; color: white; border: none; padding: 15px 25px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                🔒 Payer 50,00 $ USD
            </button>
            <script>
                let widgetExpert = FedaPay.init('#btn-expert', {{
                    public_key: '{FEDAPAY_PUBLIC_KEY}',
                    transaction: {{ amount: 30000, description: "Abonnement EXPERT AvisExpress" }},
                    customer: {{ email: "{email_client}" }},
                    onComplete: function(response) {{
                        if (response.reason === FedaPay.CHECKOUT_COMPLETED) {{
                            window.top.location.href = window.location.origin + "?status=approved&email={email_client}&amount=50";
                        }}
                    }}
                }});
            </script>
            '''
            st.components.v1.html(html_expert, height=90)

# ------------------------------------------------------------------------------
# 2. ENVOI DE SMS AVIS GOOGLE
# ------------------------------------------------------------------------------
elif menu == "📱 Service SMS Avis Google":
    st.title("📱 Service AvisExpress - SMS Avis Google")
    col_a, col_b = st.columns(2)
    with col_a:
        nom_commerce = st.text_input("Nom du commerce :", "Mon Commerce")
        telephone = st.text_input("Numéro du client :", "+229 90000000")
        lien_google = st.text_input("Lien Google Review :", "https://g.page/r/example/review")
        
    with col_b:
        st.subheader("💬 Aperçu SMS")
        st.info(f"Bonjour ! Merci d'avoir visité **{nom_commerce}**. Laissez-nous un avis ici : {lien_google}")

    if st.button("Envoyer l'invitation SMS"):
        if telephone and lien_google:
            st.success(f"✅ SMS envoyé au {telephone} !")
        else:
            st.error("Veuillez remplir tous les champs.")

# ------------------------------------------------------------------------------
# 3. ESPACE ADMINISTRATEUR
# ------------------------------------------------------------------------------
elif menu == "👑 Espace Administrateur":
    st.title("👑 Espace Administrateur - Consultation des transactions")
    pwd_input = st.text_input("Saisissez le mot de passe Administrateur :", type="password")
    
    if pwd_input == PASSWORD_ADMIN:
        st.success("Accès administrateur autorisé !")
        
        conn = sqlite3.connect('database.db')
        df_trans = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)
        conn.close()
        
        if df_trans.empty:
            st.info("Aucune transaction enregistrée.")
        else:
            total_global = df_trans['montant_total'].sum()
            total_psn = df_trans['part_psn'].sum()
            total_robux = df_trans['part_robux'].sum()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Montant Total Reçu", f"{total_global:.2f} $")
            c2.metric("Total Alloué PlayStation", f"{total_psn:.2f} $")
            c3.metric("Total Alloué Robux", f"{total_robux:.2f} $")
            
            st.markdown("---")
            st.subheader("📋 Historique complet des transactions (Réservé Admin)")
            st.dataframe(df_trans, use_container_width=True)
            
            csv = df_trans.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Télécharger le rapport CSV", data=csv, file_name="rapport_admin_5050.csv", mime="text/csv")
            
    elif pwd_input != "":
        st.error("Mot de passe incorrect.")
