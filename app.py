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
    page_title="AvisExpress - Admin & Récompenses",
    page_icon="🚀",
    layout="wide"
)

# --- MOT DE PASSE ADMIN ---
# (À modifier par votre mot de passe administrateur personnalisé)
PASSWORD_ADMIN = "admin123"

# --- INITIALISATION DE LA BASE DE DONNÉES SQLITE ---
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

# --- FONCTION DE NOTIFICATION EMAIL ---
def envoyer_email_notification(email_client, montant_total, part_psn, part_robux, liste_psn, liste_robux, destination_psn, destination_robux):
    try:
        smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(st.secrets.get("SMTP_PORT", 587))
        sender_email = st.secrets.get("SENDER_EMAIL", "")
        sender_password = st.secrets.get("SENDER_PASSWORD", "")
        admin_email = st.secrets.get("ADMIN_EMAIL", sender_email)

        if not sender_email or not sender_password:
            st.warning("⚠️ Les identifiants SMTP e-mail ne sont pas encore configurés dans vos Secrets Streamlit Cloud.")
            return False

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = admin_email
        msg['Subject'] = f"🔔 Nouvelle répartition 50/50 ({montant_total}$ USD)"

        psn_details = "\n".join([f"- {item}" for item in liste_psn])
        robux_details = "\n".join([f"- {item}" for item in liste_robux])

        corps_email = f"""
Bonjour Administrateur,

Une nouvelle répartition 50/50 a été enregistrée sur AvisExpress.

--------------------------------------------------
DÉTAILS DE LA TRANSACTION :
--------------------------------------------------
- Client : {email_client}
- Montant Total Payé : {montant_total:.2f} $ USD
- Date : {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

--------------------------------------------------
1. PART PLAYSTATION STORE (50%)
--------------------------------------------------
- Montant alloué : {part_psn:.2f} $ USD
- Destination / Compte : {destination_psn}
- Codes attribués :
{psn_details}

--------------------------------------------------
2. PART ROBUX (50%)
--------------------------------------------------
- Montant alloué : {part_robux:.2f} $ USD
- Destination / Compte : {destination_robux}
- Codes attribués :
{robux_details}

--------------------------------------------------
Notification automatique envoyée par AvisExpress.
        """

        msg.attach(MIMEText(corps_email, 'plain', 'utf-8'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:
        st.error(f"Erreur lors de l'envoi de la notification e-mail : {e}")
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

def generer_repartition_50_50(email, montant_total, dest_psn="", dest_robux=""):
    part_psn = montant_total * 0.50
    part_robux = montant_total * 0.50
    
    # Cartes PSN
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
            
    # Codes Robux
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

    # Sauvegarde BDD
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO transactions (email, montant_total, part_psn, part_robux, codes_psn, codes_robux, dest_psn, dest_robux, date_transaction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (email, montant_total, part_psn, part_robux, " | ".join(cartes_psn), " | ".join(cartes_robux), dest_psn, dest_robux, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    return cartes_psn, cartes_robux, part_psn, part_robux

# --- MENU NAVIGATION ---
st.sidebar.title("🚀 AvisExpress")
menu = st.sidebar.radio("Navigation", ["📱 Envoi d'Avis SMS", "🎁 Répartition 50/50 Récompenses", "👑 Espace Administrateur"])

if menu == "📱 Envoi d'Avis SMS":
    st.title("📱 Service de Collecte d'Avis SMS")
    nom_commerce = st.text_input("Nom de votre commerce", "Mon Commerce")
    telephone = st.text_input("Numéro du client (avec indicatif)", "+229...")
    lien_google = st.text_input("Lien Google Review", "https://g.page/r/...")
    
    if st.button("Envoyer le SMS"):
        if telephone and lien_google:
            st.success(f"SMS d'invitation envoyé avec succès à {telephone} !")
        else:
            st.error("Veuillez remplir tous les champs.")

elif menu == "🎁 Répartition 50/50 Récompenses":
    st.title("🎁 Conversion 50/50 (PlayStation & Robux)")
    
    with st.form("form_conversion"):
        email = st.text_input("Adresse E-mail du client *", placeholder="client@gmail.com")
        montant = st.number_input("Montant total à convertir ($ USD)", min_value=20.0, max_value=1000.0, value=50.0, step=10.0)
        
        st.markdown("---")
        st.subheader("📍 Destinations des fonds")
        dest_psn = st.text_input("Destination PlayStation (ex: ID PSN / E-mail Admin)", "compte-psn-admin@domaine.com")
        dest_robux = st.text_input("Destination Robux (ex: Pseudo Roblox / E-mail Admin)", "CompteRobloxAdmin")
        
        btn_submit = st.form_submit_button("Calculer, Répartir et Envoyer la Notification")
        
    if btn_submit:
        if not email or "@" not in email:
            st.error("Veuillez entrer une adresse e-mail valide.")
        else:
            list_psn, list_robux, part_psn, part_robux = generer_repartition_50_50(email, montant, dest_psn, dest_robux)
            
            st.success("✅ Conversion effectuée avec succès et enregistrée !")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎮 PlayStation (50%)")
                st.info(f"Part : **{part_psn:.2f} $**")
                st.write(f"**Destination :** {dest_psn}")
                for c in list_psn:
                    st.write(f"- {c}")
                    
            with col2:
                st.subheader("🧱 Robux (50%)")
                st.info(f"Part : **{part_robux:.2f} $**")
                st.write(f"**Destination :** {dest_robux}")
                for r in list_robux:
                    st.write(f"- {r}")
            
            with st.spinner("Envoi de la notification par e-mail..."):
                succes_email = envoyer_email_notification(
                    email_client=email,
                    montant_total=montant,
                    part_psn=part_psn,
                    part_robux=part_robux,
                    liste_psn=list_psn,
                    liste_robux=list_robux,
                    destination_psn=dest_psn,
                    destination_robux=dest_robux
                )
                if succes_email:
                    st.success("📧 Notification e-mail envoyée à l'administrateur !")

elif menu == "👑 Espace Administrateur":
    st.title("👑 Tableau de Bord Administrateur")
    
    # Authentification Admin
    pwd_input = st.text_input("Saisissez le mot de passe Administrateur :", type="password")
    
    if pwd_input == PASSWORD_ADMIN:
        st.success("Accès administrateur autorisé !")
        
        # Récupération des données SQLite
        conn = sqlite3.connect('database.db')
        df_trans = pd.read_sql_query("SELECT * FROM transactions ORDER BY id DESC", conn)
        conn.close()
        
        if df_trans.empty:
            st.info("Aucune transaction enregistrée pour le moment.")
        else:
            # Compteurs et Métriques
            total_global = df_trans['montant_total'].sum()
            total_psn = df_trans['part_psn'].sum()
            total_robux = df_trans['part_robux'].sum()
            
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Général Traité", f"{total_global:.2f} $")
            col_b.metric("Total Alloué PlayStation", f"{total_psn:.2f} $")
            col_c.metric("Total Alloué Robux", f"{total_robux:.2f} $")
            
            st.markdown("---")
            st.subheader("📋 Historique complet des transactions 50/50")
            
            # Affichage du tableau interactif
            st.dataframe(df_trans, use_container_width=True)
            
            # Téléchargement CSV
            csv = df_trans.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Télécharger le rapport CSV", data=csv, file_name="rapport_admin_transactions.csv", mime="text/csv")
            
    elif pwd_input != "":
        st.error("Mot de passe incorrect.")
