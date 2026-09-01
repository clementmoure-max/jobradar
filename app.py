import streamlit as st
import requests
import re
import os
import math
import json
import pandas as pd
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv

# ==============================================================================
# CONFIGURATION & THÈME CHATOYANT (GLASSMORPHISM & ACCENTS LUMINEUX)
# ==============================================================================
st.set_page_config(
    page_title="JobRadar — Cournonsec",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2.5rem;
        max-width: 1280px;
    }

    /* Titre Principal avec Dégradé */
    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60a5fa 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }

    /* Métriques en bandeau */
    .metric-card {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.7));
        border: 1px solid rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(12px);
        border-radius: 12px;
        padding: 12px 18px;
        text-align: center;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.3);
    }
    .metric-val {
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    /* Cartes d'offres dynamiques */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 14px;
        padding: 16px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(168, 85, 247, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 10px 25px -5px rgba(168, 85, 247, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    }

    /* Badges Lumineux */
    .badge-source {
        font-size: 11px;
        padding: 3px 9px;
        border-radius: 6px;
        background: rgba(59, 130, 246, 0.15);
        color: #93c5fd;
        font-weight: 600;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    .badge-dist {
        font-size: 12px;
        font-weight: 700;
        color: #34d399;
        background: rgba(16, 185, 129, 0.12);
        padding: 2px 8px;
        border-radius: 6px;
        border: 1px solid rgba(16, 185, 129, 0.25);
    }
    
    .badge-salaire {
        font-size: 11px;
        font-weight: 700;
        color: #fbbf24;
        background: rgba(245, 158, 11, 0.12);
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(245, 158, 11, 0.25);
        display: inline-block;
        margin-top: 4px;
    }
    
    .badge-interim {
        font-size: 11px;
        font-weight: 700;
        color: #f472b6;
        background: rgba(236, 72, 153, 0.12);
        padding: 2px 7px;
        border-radius: 6px;
        border: 1px solid rgba(236, 72, 153, 0.3);
    }

    .badge-cpf {
        font-size: 11px;
        font-weight: 700;
        color: #c084fc;
        background: rgba(168, 85, 247, 0.15);
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(168, 85, 247, 0.3);
    }

    .badge-modalite {
        font-size: 11px;
        font-weight: 600;
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.12);
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(56, 189, 248, 0.25);
    }

    /* Onglets modernes */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0px 0px;
        padding: 8px 16px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

load_dotenv()
FT_CLIENT_ID = os.getenv("FT_CLIENT_ID")
FT_CLIENT_SECRET = os.getenv("FT_CLIENT_SECRET")
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

LAT_REF = 43.5485
LON_REF = 3.7022
INSEE_COURNONSEC = "34087"
FAVORIS_FILE = "favoris.json"

st.markdown('<div class="hero-title">⚡ JobRadar — Cournonsec</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Moteur unifié d\'emploi, intérim et formations financées CPF sur le bassin Montpellier / Occitanie</div>', unsafe_allow_html=True)

# ==============================================================================
# GESTION DES FAVORIS & ÉTAT DE SESSION
# ==============================================================================
def charger_favoris():
    if os.path.exists(FAVORIS_FILE):
        try:
            with open(FAVORIS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def sauvegarder_favoris(favoris):
    with open(FAVORIS_FILE, "w", encoding="utf-8") as f:
        json.dump(favoris, f, ensure_ascii=False, indent=2)

if "favoris" not in st.session_state:
    st.session_state.favoris = charger_favoris()

if "page_courante" not in st.session_state:
    st.session_state.page_courante = 1

def aller_page_precedente():
    if st.session_state.page_courante > 1:
        st.session_state.page_courante -= 1

def aller_page_suivante(max_p):
    if st.session_state.page_courante < max_p:
        st.session_state.page_courante += 1

def changer_page_select():
    st.session_state.page_courante = st.session_state.select_page_input

# ==============================================================================
# NETTOYAGE DU TITRE
# ==============================================================================
def epurer_titre(titre):
    if not titre:
        return "Poste sans titre"
    t = re.sub(r'[\(\[\{/\s]*[hH]\s*[\/|\-]?\s*[fF][\)\]\}\/\s]*', ' ', titre)
    t = re.sub(r'\s+', ' ', t).strip()
    return f"{t} (H/F)"

# ==============================================================================
# CALCUL DE DISTANCE & GÉOCODAGE
# ==============================================================================
def calculer_distance_km(lat1, lon1, lat2, lon2):
    if not all([lat1, lon1, lat2, lon2]):
        return 999.0
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return round(r * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))), 1)

@st.cache_data(ttl=86400)
def geocoder_commune(nom_lieu):
    if not nom_lieu or str(nom_lieu).lower() in ("lieu non précisé", "france", "none", ""):
        return None, None
    try:
        url = "https://api-adresse.data.gouv.fr/search/"
        params = {"q": nom_lieu, "limit": 1, "lat": LAT_REF, "lon": LON_REF}
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get("features"):
                coords = data["features"][0]["geometry"]["coordinates"]
                return coords[1], coords[0]
    except Exception:
        pass
    return None, None

# ==============================================================================
# CONNECTEURS API EMPLOI
# ==============================================================================
@st.cache_data(ttl=900, show_spinner=False)
def fetch_france_travail(rayon, filtre_interim_seul=False):
    if not FT_CLIENT_ID or not FT_CLIENT_SECRET:
        return []
    try:
        auth_url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": FT_CLIENT_ID,
            "client_secret": FT_CLIENT_SECRET,
            "scope": "o2dsoffre api_offresdemploiv2",
        }
        token_resp = requests.post(auth_url, data=auth_data, timeout=5)
        if token_resp.status_code != 200:
            return []
        token = token_resp.json().get("access_token")
        search_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        params = {"commune": INSEE_COURNONSEC, "distance": rayon, "sort": 1}
        
        if filtre_interim_seul:
            params["natureContrat"] = "E2"

        res = requests.get(search_url, headers=headers, params=params, timeout=5)
        if res.status_code in (200, 206):
            resultats = []
            for item in res.json().get("resultats", []):
                lieu_info = item.get("lieuTravail", {})
                lat = float(lieu_info.get("latitude")) if lieu_info.get("latitude") else None
                lon = float(lieu_info.get("longitude")) if lieu_info.get("longitude") else None
                dist = calculer_distance_km(LAT_REF, LON_REF, lat, lon)

                duree_txt = item.get("dureeTravailLibelleConverti", item.get("dureeTravailLibelleTempsPartiel", ""))
                est_temps_plein = "plein" in duree_txt.lower() or item.get("tempsPlein") is True

                sal = item.get("salaire", {}).get("libelle", "")
                if sal.lower() in ("non précisé", "selon profil", ""):
                    sal = None

                resultats.append({
                    "id": f"ft_{item.get('id', '')}",
                    "source": "France Travail",
                    "titre": epurer_titre(item.get("intitule")),
                    "entreprise": item.get("entreprise", {}).get("nom", "Confidentiel"),
                    "lieu": lieu_info.get("libelle", "Non précisé"),
                    "lat": lat,
                    "lon": lon,
                    "distance": dist,
                    "contrat": item.get("typeContratLibelle", item.get("typeContrat", "Contrat non précisé")),
                    "type_temps": "Temps plein" if est_temps_plein else "Temps partiel",
                    "salaire": sal,
                    "description": item.get("description", "Pas de description fournie."),
                    "url": item.get("origineOffre", {}).get("urlOrigine", "#")
                })
            return resultats
        return []
    except Exception:
        return []

@st.cache_data(ttl=900, show_spinner=False)
def fetch_adzuna(rayon):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    try:
        url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "where": "Montpellier",
            "distance": rayon,
            "results_per_page": 50
        }

        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            resultats = []
            for item in res.json().get("results", []):
                lat = float(item.get("latitude")) if item.get("latitude") else None
                lon = float(item.get("longitude")) if item.get("longitude") else None
                lieu_nom = item.get("location", {}).get("display_name", "Non précisé")
                
                if not lat or not lon:
                    lat, lon = geocoder_commune(lieu_nom)
                dist = calculer_distance_km(LAT_REF, LON_REF, lat, lon)

                temps_txt = "Temps partiel" if item.get("contract_time") == "part_time" else "Temps plein"
                
                sal = None
                if item.get("salary_min"):
                    sal = f"{int(item.get('salary_min'))} - {int(item.get('salary_max', item.get('salary_min')))} €/an"

                resultats.append({
                    "id": f"adz_{item.get('id', '')}",
                    "source": "Adzuna",
                    "titre": epurer_titre(item.get("title")),
                    "entreprise": item.get("company", {}).get("display_name", "Confidentiel"),
                    "lieu": lieu_nom,
                    "lat": lat,
                    "lon": lon,
                    "distance": dist,
                    "contrat": item.get("contract_type", "Non précisé"),
                    "type_temps": temps_txt,
                    "salaire": sal,
                    "description": item.get("description", "Pas de description fournie."),
                    "url": item.get("redirect_url", "#")
                })
            return resultats
        return []
    except Exception:
        return []

@st.cache_data(ttl=900, show_spinner=False)
def fetch_jooble(rayon):
    if not JOOBLE_API_KEY:
        return []
    try:
        url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
        payload = {"keywords": "interim emploi", "location": "Montpellier", "radius": str(rayon), "page": "1"}
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        if res.status_code == 200:
            resultats = []
            for item in res.json().get("jobs", []):
                lieu_nom = item.get("location", "Non précisé")
                lat, lon = geocoder_commune(lieu_nom)
                dist = calculer_distance_km(LAT_REF, LON_REF, lat, lon)

                texte_brut = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
                temps_txt = "Temps partiel" if ("partiel" in texte_brut or "mi-temps" in texte_brut) else "Temps plein"

                sal = item.get("salary", "")
                if sal.lower() in ("non précisé", ""):
                    sal = None

                resultats.append({
                    "id": f"jb_{item.get('id', '')}",
                    "source": "Jooble",
                    "titre": epurer_titre(item.get("title")),
                    "entreprise": item.get("company", "Confidentiel"),
                    "lieu": lieu_nom,
                    "lat": lat,
                    "lon": lon,
                    "distance": dist,
                    "contrat": item.get("type", "Non précisé"),
                    "type_temps": temps_txt,
                    "salaire": sal,
                    "description": item.get("snippet", "Pas de description fournie."),
                    "url": item.get("link", "#")
                })
            return resultats
        return []
    except Exception:
        return []

@st.cache_data(ttl=900, show_spinner=False)
def fetch_jsearch(rayon):
    if not RAPIDAPI_KEY:
        return []
    try:
        url = "https://jsearch.p.rapidapi.com/search"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
        params = {
            "query": "jobs in Montpellier, France",
            "page": "1",
            "num_pages": "1",
            "employment_types": "FULLTIME,PARTTIME,CONTRACTOR"
        }

        res = requests.get(url, headers=headers, params=params, timeout=6)
        if res.status_code == 200:
            resultats = []
            for item in res.json().get("data", []):
                lat = float(item.get("job_latitude")) if item.get("job_latitude") else None
                lon = float(item.get("job_longitude")) if item.get("job_longitude") else None
                lieu_nom = item.get("job_city") or item.get("job_location", "Montpellier")
                if not lat or not lon:
                    lat, lon = geocoder_commune(lieu_nom)
                dist = calculer_distance_km(LAT_REF, LON_REF, lat, lon)

                temps_txt = "Temps partiel" if item.get("job_employment_type") == "PARTTIME" else "Temps plein"

                sal = None
                if item.get("job_min_salary"):
                    sal = f"{item.get('job_min_salary')} - {item.get('job_max_salary')} €"

                resultats.append({
                    "id": f"js_{item.get('job_id', '')[:12]}",
                    "source": "JSearch (Indeed/LinkedIn)",
                    "titre": epurer_titre(item.get("job_title")),
                    "entreprise": item.get("employer_name", "Confidentiel"),
                    "lieu": lieu_nom,
                    "lat": lat,
                    "lon": lon,
                    "distance": dist,
                    "contrat": item.get("job_employment_type", "Non précisé"),
                    "type_temps": temps_txt,
                    "salaire": sal,
                    "description": item.get("job_description", "Pas de description fournie."),
                    "url": item.get("job_apply_link", "#")
                })
            return resultats
        return []
    except Exception:
        return []

# ==============================================================================
# CONNECTEUR FORMATIONS CPF (LOCAL + DISTANCIEL ÉLARGI)
# ==============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_formations_cpf(mot_cle="", modalite_choisie="Tous"):
    catalogue = [
        {"titre": "CACES R489 Chariots Élévateurs (Catégories 1A, 3, 5)", "organisme": "AFTRAL Pérols", "domaine": "Logistique / Manutention", "lieu": "Pérols (34)", "modalite": "Présentiel", "cout": 850.0, "code_rncp": "RS5054"},
        {"titre": "CACES R486 Nacelles Élévatrices (PEMP 1B - 3B)", "organisme": "APAVE Sud Montpellier", "domaine": "Logistique / BTP", "lieu": "Lattes (34)", "modalite": "Présentiel", "cout": 750.0, "code_rncp": "RS5084"},
        {"titre": "Titre Professionnel Préparateur de Commandes en Entrepôt", "organisme": "Promotrans Mauguio", "domaine": "Logistique", "lieu": "Mauguio (34)", "modalite": "Présentiel", "cout": 1800.0, "code_rncp": "RNCP35111"},
        {"titre": "Titre Professionnel Cariste d'Entrepôt", "organisme": "AFTRAL Pérols", "domaine": "Logistique", "lieu": "Pérols (34)", "modalite": "Présentiel", "cout": 1950.0, "code_rncp": "RNCP34858"},
        {"titre": "Permis B - Formation Complète Code + Conduite", "organisme": "Auto-École Labellisée CPF", "domaine": "Transport / Mobilité", "lieu": "Saint-Jean-de-Védas (34)", "modalite": "Mixte", "cout": 1200.0, "code_rncp": "RS5194"},
        {"titre": "Permis C (Poids Lourd) + FIMO Marchandises", "organisme": "AFTRAL Pérols", "domaine": "Transport Routier", "lieu": "Pérols (34)", "modalite": "Présentiel", "cout": 2800.0, "code_rncp": "RNCP34856"},
        {"titre": "Titre Professionnel Conducteur Livreur Véhicules Légers", "organisme": "Promotrans Mauguio", "domaine": "Transport / Livraison", "lieu": "Mauguio (34)", "modalite": "Présentiel", "cout": 2100.0, "code_rncp": "RNCP34857"},
        {"titre": "FCO Transport de Marchandises (Renouvellement)", "organisme": "ECF Sud Montpellier", "domaine": "Transport Routier", "lieu": "Montpellier (34)", "modalite": "Présentiel", "cout": 650.0, "code_rncp": "RS5112"},
        {"titre": "CACES R482 Engins de Chantier (Catégories A, B1, C1)", "organisme": "APAVE Sud Montpellier", "domaine": "BTP / Travaux Publics", "lieu": "Lattes (34)", "modalite": "Présentiel", "cout": 1100.0, "code_rncp": "RS5083"},
        {"titre": "Habilitation Électrique B0 / H0 / H0V / B1V", "organisme": "DEKRA Formation", "domaine": "Sécurité / Électricité", "lieu": "Saint-Aunès (34)", "modalite": "Présentiel", "cout": 420.0, "code_rncp": "RS5487"},
        {"titre": "CQP APS - Agent de Prévention et de Sécurité", "organisme": "IFSP Montpellier", "domaine": "Sécurité Privée", "lieu": "Montpellier (34)", "modalite": "Présentiel", "cout": 1450.0, "code_rncp": "RNCP37841"},
        {"titre": "SSIAP 1 - Service de Sécurité Incendie et Assistance", "organisme": "FORMA-SUD", "domaine": "Sécurité Incendie", "lieu": "Pignan (34)", "modalite": "Présentiel", "cout": 980.0, "code_rncp": "RS5310"},
        {"titre": "SST - Sauveteur Secouriste du Travail", "organisme": "Croix-Rouge Compétence", "domaine": "Santé / Secourisme", "lieu": "Montpellier (34)", "modalite": "Présentiel", "cout": 290.0, "code_rncp": "RS5051"},
        {"titre": "Hygiène Alimentaire Restauration Commerciale (HACCP)", "organisme": "UMIH Formation Hérault", "domaine": "Restauration / Hôtellerie", "lieu": "Montpellier (34)", "modalite": "Présentiel", "cout": 350.0, "code_rncp": "RS5190"},
        {"titre": "Titre Professionnel Assistant(e) de Vie aux Familles (ADVD)", "organisme": "GRETA Montpellier Littoral", "domaine": "Santé / Services", "lieu": "Montpellier (34)", "modalite": "Présentiel", "cout": 2400.0, "code_rncp": "RNCP35993"},
        {"titre": "Certification TOSA Excel Complet (Débutant à Avancé)", "organisme": "Académie Digitale France", "domaine": "Bureautique", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 490.0, "code_rncp": "RS5252"},
        {"titre": "TOSA Pack Office Complet (Word, Excel, PowerPoint, Outlook)", "organisme": "CCI Formation E-learning", "domaine": "Bureautique", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 890.0, "code_rncp": "RS5254"},
        {"titre": "Anglais Professionnel Certifiant TOEIC / Linguaskill", "organisme": "Global Exam / WSE", "domaine": "Langues", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 1150.0, "code_rncp": "RS5500"},
        {"titre": "Espagnol Professionnel Certifié (DELE / SIELE)", "organisme": "Institut des Langues en Ligne", "domaine": "Langues", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 850.0, "code_rncp": "RS5340"},
        {"titre": "Création & Gestion d'Entreprise (Micro-Entreprise / SASU)", "organisme": "BGE France E-learning", "domaine": "Entrepreneuriat", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 950.0, "code_rncp": "RS5402"},
        {"titre": "Comptabilité Générale & Logiciel Ciel/Sage (Certification)", "organisme": "ComptaPass Formation", "domaine": "Comptabilité / Gestion", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 1390.0, "code_rncp": "RS5620"},
        {"titre": "Titre Professionnel Gestionnaire de Paie", "organisme": "Studi / En Ligne", "domaine": "Ressources Humaines / Paie", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 2600.0, "code_rncp": "RNCP37948"},
        {"titre": "Marketing Digital & Réseaux Sociaux (RS5217)", "organisme": "LiveMentor Formation", "domaine": "Communication / Web", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 1500.0, "code_rncp": "RS5217"},
        {"titre": "Développeur Web & Web Mobile (HTML, CSS, JavaScript, PHP)", "organisme": "OpenClassrooms", "domaine": "Informatique / Dév", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 3200.0, "code_rncp": "RNCP37674"},
        {"titre": "Concepteur Designer Graphique (Photoshop, Illustrator, InDesign)", "organisme": "École Française", "domaine": "Design / Graphisme", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 1690.0, "code_rncp": "RNCP34438"},
        {"titre": "Techniques de Vente & Négociation Commerciale", "organisme": "VentePro Academy", "domaine": "Commerce / Vente", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 1250.0, "code_rncp": "RS5410"},
        {"titre": "Certification Cybersécurité & Protection des Données (RGPD)", "organisme": "CyberCampus France", "domaine": "Informatique / Sécurité", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 1490.0, "code_rncp": "RS5588"},
        {"titre": "Titre Professionnel Secrétaire Assistant(e) Médico-Social", "organisme": "Centre Européen de Formation", "domaine": "Santé / Secrétariat", "lieu": "100% En Ligne (France)", "modalite": "À distance", "cout": 2200.0, "code_rncp": "RNCP36805"}
    ]

    for item in catalogue:
        item["url"] = "https://www.moncompteformation.gouv.fr/espace-prive/html/#/formation/recherche"

    if modalite_choisie == "💻 À distance (E-learning)":
        catalogue = [f for f in catalogue if "distance" in f["modalite"].lower()]
    elif modalite_choisie == "🏫 Présentiel / Mixte":
        catalogue = [f for f in catalogue if "distance" not in f["modalite"].lower() or "mixte" in f["modalite"].lower()]

    if mot_cle.strip():
        m = mot_cle.strip().lower()
        return [
            f for f in catalogue
            if m in f["titre"].lower()
            or m in f["domaine"].lower()
            or m in f["organisme"].lower()
            or m in f["lieu"].lower()
            or m in f.get("code_rncp", "").lower()
        ]

    return catalogue

# ==============================================================================
# FILTRAGE EN MÉMOIRE
# ==============================================================================
def nettoyer(texte):
    return re.sub(r'[^a-zA-Z0-9]', '', str(texte).lower())

def appliquer_filtres(offres, sources_actives, type_temps, types_contrats, mot_cle, exclusions, max_dist):
    mots_inclus = [m.strip().lower() for m in mot_cle.split() if m.strip()]
    mots_exclus = [e.strip().lower() for e in exclusions.split(",") if e.strip()]

    vues = set()
    resultats = []

    for o in offres:
        if o.get("source") not in sources_actives:
            continue

        if o["distance"] > max_dist and o["distance"] != 999.0:
            continue

        if type_temps == "Temps partiel" and o["type_temps"] != "Temps partiel":
            continue
        elif type_temps == "Temps plein" and o["type_temps"] != "Temps plein":
            continue

        if types_contrats:
            c_label = o.get("contrat", "").lower()
            correspond = False
            for tc in types_contrats:
                if tc.lower() in c_label or (tc == "Autre" and not any(k in c_label for k in ["cdi", "cdd", "intérim", "interim"])):
                    correspond = True
                    break
            if not correspond:
                continue

        texte_complet = f"{o['titre']} {o['entreprise']} {o['description']}".lower()

        if any(m in texte_complet for m in mots_exclus):
            continue

        if mots_inclus and not all(m in texte_complet for m in mots_inclus):
            continue

        cle = f"{nettoyer(o['titre'])[:15]}_{nettoyer(o['entreprise'])}_{nettoyer(o['lieu'])[:8]}"
        if cle not in vues:
            vues.add(cle)
            resultats.append(o)

    return sorted(resultats, key=lambda x: x["distance"])

# ==============================================================================
# BARRE LATÉRALE & PARAMÈTRES
# ==============================================================================
SOURCES_DISPONIBLES = ["France Travail", "Adzuna", "Jooble", "JSearch (Indeed/LinkedIn)"]
CONTRATS_DISPONIBLES = ["CDI", "CDD", "Intérim", "Autre"]

with st.sidebar:
    st.markdown("### ⚙️ **Filtres de recherche**")

    sources_selectionnees = st.multiselect(
        "🌐 Agrégateurs actifs",
        options=SOURCES_DISPONIBLES,
        default=SOURCES_DISPONIBLES
    )

    type_temps_choisi = st.radio(
        "⏳ Temps de travail",
        ["Tous", "Temps partiel", "Temps plein"],
        index=0
    )

    contrats_choisis = st.multiselect(
        "📄 Types de contrat",
        options=CONTRATS_DISPONIBLES,
        default=CONTRATS_DISPONIBLES
    )

    distance_km = st.slider("Rayon (km)", min_value=5, max_value=50, value=25, step=5)
    mot_cle_input = st.text_input("🔍 Métier / Mots-clés", placeholder="Ex: Chauffeur, Adecco, Vente...")
    mots_a_exclure_input = st.text_input("🚫 Exclusions", "stage, alternance, indépendant")

    st.divider()
    if st.button("✨ Forcer l'actualisation", use_container_width=True):
        st.cache_data.clear()
        st.session_state.page_courante = 1
        st.rerun()

# Récupération des données
toutes_offres = []
interim_uniquement = (contrats_choisis == ["Intérim"])

if "France Travail" in sources_selectionnees:
    toutes_offres.extend(fetch_france_travail(distance_km, filtre_interim_seul=interim_uniquement))
if "Adzuna" in sources_selectionnees:
    toutes_offres.extend(fetch_adzuna(distance_km))
if "Jooble" in sources_selectionnees:
    toutes_offres.extend(fetch_jooble(distance_km))
if "JSearch (Indeed/LinkedIn)" in sources_selectionnees:
    toutes_offres.extend(fetch_jsearch(distance_km))

offres_finales = appliquer_filtres(
    toutes_offres,
    sources_selectionnees,
    type_temps_choisi,
    contrats_choisis,
    mot_cle_input,
    mots_a_exclure_input,
    distance_km
)

# ==============================================================================
# ONGLETS PRINCIPAUX AVEC LOOK ÉPURÉ
# ==============================================================================
tab_recherche, tab_carte, tab_suivi, tab_cpf = st.tabs([
    f"🚀 Opportunités ({len(offres_finales)})",
    "📍 Carte en direct",
    f"⭐ Candidatures ({len(st.session_state.favoris)})",
    "🎓 Formations CPF"
])

# --- ONGLET 1 : EXPLORATEUR D'OFFRES ---
with tab_recherche:
    # Bandeau métriques chatoyant
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(offres_finales)}</div><div class="metric-label">Offres Disponibles</div></div>', unsafe_allow_html=True)
    with m2:
        nb_proches = len([o for o in offres_finales if o['distance'] <= 10])
        st.markdown(f'<div class="metric-card"><div class="metric-val">{nb_proches}</div><div class="metric-label">&le; 10 km de Cournonsec</div></div>', unsafe_allow_html=True)
    with m3:
        nb_interim = len([o for o in offres_finales if "intérim" in o['contrat'].lower() or "interim" in o['contrat'].lower()])
        st.markdown(f'<div class="metric-card"><div class="metric-val">{nb_interim}</div><div class="metric-label">Missions Intérim</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(st.session_state.favoris)}</div><div class="metric-label">Postes Suivis</div></div>', unsafe_allow_html=True)

    st.write("")

    if not offres_finales:
        st.info("💡 Aucune offre trouvée avec ces critères. Ajustez vos filtres ou étendez le rayon.")
    else:
        nb_par_page = 15
        nb_pages = max(1, math.ceil(len(offres_finales) / nb_par_page))

        if st.session_state.page_courante > nb_pages:
            st.session_state.page_courante = 1

        c_top1, c_top2 = st.columns([3, 1])
        with c_top1:
            st.caption(f"Affichage de la page {st.session_state.page_courante} sur {nb_pages} — Trié par proximité")
        with c_top2:
            if nb_pages > 1:
                st.selectbox(
                    "Page",
                    range(1, nb_pages + 1),
                    index=st.session_state.page_courante - 1,
                    key="select_page_input",
                    on_change=changer_page_select,
                    label_visibility="collapsed"
                )

        debut = (st.session_state.page_courante - 1) * nb_par_page
        fin = debut + nb_par_page

        for offre in offres_finales[debut:fin]:
            offre_id = offre["id"]
            est_enregistre = offre_id in st.session_state.favoris
            dist_str = f"📍 {offre['distance']} km" if offre['distance'] < 900 else "📍 Distance inconnue"
            est_interim = any(k in offre['contrat'].lower() for k in ["intérim", "interim", "temporaire"])

            with st.container(border=True):
                st.markdown(f"<h4 style='margin-bottom: 4px; color: #f8fafc;'>{offre['titre']}</h4>", unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns([2.2, 2, 1.2])
                c1.markdown(f"🏢 **{offre['entreprise']}** <span style='color:#64748b;'>&bull; {offre['lieu']}</span>", unsafe_allow_html=True)
                
                contrat_badge = f"<span class='badge-interim'>⚡ {offre['contrat']}</span>" if est_interim else f"📄 <span style='color:#cbd5e1;'>{offre['contrat']}</span>"
                c2.markdown(f"<span class='badge-dist'>{dist_str}</span> &nbsp; {contrat_badge} <span style='font-size:12px; color:#64748b;'>({offre['type_temps']})</span>", unsafe_allow_html=True)
                c3.markdown(f"<span class='badge-source'>{offre['source']}</span>", unsafe_allow_html=True)

                if offre["salaire"]:
                    st.markdown(f"<span class='badge-salaire'>💶 Rémunération : {offre['salaire']}</span>", unsafe_allow_html=True)

                with st.expander("📄 Aperçu détaillé du poste"):
                    st.write(offre['description'])

                b1, b2 = st.columns([1.2, 4])
                with b1:
                    if not est_enregistre:
                        if st.button("⭐ Suivre", key=f"btn_save_{offre_id}"):
                            st.session_state.favoris[offre_id] = {**offre, "statut": "À postuler", "notes": ""}
                            sauvegarder_favoris(st.session_state.favoris)
                            st.rerun()
                    else:
                        st.caption("✅ **Candidature suivie**")
                with b2:
                    if offre['url'] != "#":
                        st.link_button("👉 Postuler à cette offre", offre['url'])

        # Navigation en bas
        if nb_pages > 1:
            st.write("")
            col_prec, col_info, col_suiv = st.columns([1.5, 2, 1.5])

            with col_prec:
                st.button(
                    "◀ Page précédente",
                    use_container_width=True,
                    disabled=(st.session_state.page_courante <= 1),
                    on_click=aller_page_precedente,
                    key="btn_prec_bas"
                )

            with col_info:
                st.markdown(
                    f"<p style='text-align: center; margin-top: 6px; font-weight: 700; color: #a855f7;'>Page {st.session_state.page_courante} / {nb_pages}</p>",
                    unsafe_allow_html=True
                )

            with col_suiv:
                st.button(
                    "Page suivante ▶",
                    use_container_width=True,
                    disabled=(st.session_state.page_courante >= nb_pages),
                    on_click=aller_page_suivante,
                    args=(nb_pages,),
                    key="btn_suiv_bas"
                )

# --- ONGLET 2 : CARTE RADAR ---
with tab_carte:
    st.write("### 📍 Répartition géographique des offres")
    st.caption("Visualisez les opportunités les plus proches de Cournonsec en temps réel.")

    carte = folium.Map(location=[LAT_REF, LON_REF], zoom_start=11, tiles="CartoDB dark_matter")

    folium.Marker(
        location=[LAT_REF, LON_REF],
        popup="<b>🏠 Domicile (Cournonsec)</b>",
        tooltip="Cournonsec",
        icon=folium.Icon(color="red", icon="home")
    ).add_to(carte)

    for o in offres_finales:
        if o.get("lat") and o.get("lon"):
            dist_txt = f"{o['distance']} km" if o['distance'] < 900 else "N/C"
            lien_html = f"<br><a href='{o['url']}' target='_blank' style='color:#a855f7; font-weight:bold;'>👉 Postuler</a>" if o.get('url') and o['url'] != "#" else ""

            popup_html = f"""
            <div style="font-family:'Plus Jakarta Sans', sans-serif; font-size:12px; min-width:200px; color:#0f172a;">
                <b style="color:#6b21a8; font-size:13px;">{o['titre']}</b><br>
                <span style="color:#334155;">🏢 <b>{o['entreprise']}</b></span><br>
                <span>📍 {o['lieu']} (<b>{dist_txt}</b>)</span><br>
                <span style="font-size:11px; color:#64748b;">Source: {o['source']}</span>
                {lien_html}
            </div>
            """
            folium.Marker(
                location=[o["lat"], o["lon"]],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{o['titre']} — {o['entreprise']}",
                icon=folium.Icon(color="purple", icon="briefcase")
            ).add_to(carte)

    st_folium(carte, width="100%", height=580, returned_objects=[])

# --- ONGLET 3 : SUIVI DES CANDIDATURES ---
with tab_suivi:
    st.write("### ⭐ Mon Tableau de Bord Candidatures")
    if not st.session_state.favoris:
        st.info("Aucun poste suivi pour le moment. Cliquez sur '⭐ Suivre' sur une offre pour la retrouver ici.")
    else:
        statuts_liste = ["À postuler", "Candidature envoyée", "Entretien prévu", "Refusé / Sans suite"]

        for oid, f_offre in list(st.session_state.favoris.items()):
            with st.container(border=True):
                st.markdown(f"#### {f_offre['titre']} — {f_offre['entreprise']}")
                dist_txt = f"📍 {f_offre.get('distance', 999)} km" if f_offre.get('distance', 999) < 900 else ""
                st.caption(f"{f_offre['lieu']} | {dist_txt} | 📄 {f_offre.get('contrat', '')} | 🌐 {f_offre.get('source', '')}")

                col_s, col_d = st.columns([3, 1])
                with col_s:
                    idx_statut = statuts_liste.index(f_offre.get("statut", "À postuler")) if f_offre.get("statut") in statuts_liste else 0
                    nouveau_statut = st.selectbox("Statut", statuts_liste, index=idx_statut, key=f"st_{oid}")
                    if nouveau_statut != f_offre.get("statut"):
                        st.session_state.favoris[oid]["statut"] = nouveau_statut
                        sauvegarder_favoris(st.session_state.favoris)
                        st.rerun()

                with col_d:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Supprimer", key=f"del_{oid}"):
                        del st.session_state.favoris[oid]
                        sauvegarder_favoris(st.session_state.favoris)
                        st.rerun()

                note_txt = f_offre.get("notes", "")
                nouvelle_note = st.text_area("Mémos personnels", value=note_txt, key=f"nt_{oid}", height=70, placeholder="Contact RH, date relance, impressions...")
                if nouvelle_note != note_txt:
                    st.session_state.favoris[oid]["notes"] = nouvelle_note
                    sauvegarder_favoris(st.session_state.favoris)

                if f_offre.get('url') and f_offre['url'] != "#":
                    st.link_button("🔗 Revoir l'annonce d'origine", f_offre['url'])

# --- ONGLET 4 : CATALOGUE CPF ---
with tab_cpf:
    st.write("### 🎓 Formations Certifiantes Financées par MonCompteFormation")
    st.caption("Explorez les formations éligibles au CPF en présentiel dans l'Hérault ou 100% en ligne.")

    col_cpf1, col_cpf2, col_cpf3 = st.columns([2, 1.2, 1])
    with col_cpf1:
        recherche_formation = st.text_input("Rechercher une formation / diplôme", placeholder="Ex: Excel, CACES, Anglais, Comptabilité, Web...")
    with col_cpf2:
        modalite_choix = st.selectbox("Format", ["Tous", "💻 À distance (E-learning)", "🏫 Présentiel / Mixte"])
    with col_cpf3:
        budget_cpf = st.number_input("💰 Mon Budget CPF (€)", min_value=0, max_value=10000, value=1500, step=100)

    formations = fetch_formations_cpf(recherche_formation, modalite_choix)

    if not formations:
        st.info("Aucune formation ne correspond à vos critères de recherche.")
    else:
        st.write(f"**{len(formations)} formation(s)** certifiante(s) disponible(s) :")
        for f in formations:
            with st.container(border=True):
                st.markdown(f"#### {f['titre']}")
                col_info1, col_info2 = st.columns([2, 1.2])
                with col_info1:
                    st.markdown(f"🏫 **{f['organisme']}** &bull; 📍 {f['lieu']}", unsafe_allow_html=True)
                    st.caption(f"Secteur : {f['domaine']}")
                
                with col_info2:
                    st.markdown(f"<span class='badge-cpf'>Éligible CPF</span> &nbsp; <span class='badge-modalite'>{f['modalite']}</span>", unsafe_allow_html=True)
                    
                    st.write("")
                    if f["cout"] is not None:
                        reste = max(0.0, f["cout"] - budget_cpf)
                        if reste == 0:
                            st.markdown(f"💶 **Coût : {int(f['cout'])} €** <span style='color:#34d399; font-weight:600;'>(100% Pris en charge)</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"💶 **Coût : {int(f['cout'])} €** <span style='color:#f43f5e;'>*(Reste à charge : {int(reste)} €)*</span>", unsafe_allow_html=True)
                    else:
                        st.caption("Tarification sur devis")

                if f.get("code_rncp"):
                    st.caption(f"Fiche Répertoire Officiel : {f['code_rncp']}")

                st.link_button("Consulter sur MonCompteFormation.gouv.fr", f["url"])
