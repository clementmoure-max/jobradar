import os
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv

# Chargement .env local si présent
load_dotenv()

# Configuration Streamlit optimisée Mobile
st.set_page_config(
    page_title="JobRadar Sud",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"  # Replié pour laisser tout l'écran au smartphone
)

# -------------------------------------------------------------
# CSS PERSONNALISÉ ULTRA-OPTIMISÉ SMARTPHONE (PWA Style)
# -------------------------------------------------------------
st.markdown("""
<style>
    /* Réduction des marges sur écran mobile */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 100% !important;
    }
    
    /* Style carte d'offre d'emploi (App-like) */
    .job-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    
    .job-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
        line-height: 1.3;
    }
    
    .job-company {
        font-size: 0.95rem;
        font-weight: 600;
        color: #2563eb;
        margin-bottom: 8px;
    }
    
    .job-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 10px;
    }
    
    .badge {
        font-size: 0.75rem;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 500;
    }
    .badge-loc { background-color: #f1f5f9; color: #475569; }
    .badge-contract { background-color: #eff6ff; color: #1d4ed8; }
    .badge-salary { background-color: #ecfdf5; color: #047857; }
    .badge-source { background-color: #fef3c7; color: #b45309; font-weight: 600; }
    
    .job-desc {
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.4;
        margin-bottom: 12px;
    }
    
    /* Bouton tactile pleine largeur */
    .stButton > button, .stLinkButton > a {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
    }
    
    /* Masquer le menu hamburger Streamlit par défaut */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# RÉCUPÉRATION DES CLÉS SÉCURISÉES
# -------------------------------------------------------------
def get_secret(key, default=""):
    return st.secrets.get(key, os.getenv(key, default))

FT_CLIENT_ID = get_secret("FT_CLIENT_ID")
FT_CLIENT_SECRET = get_secret("FT_CLIENT_SECRET")
ADZUNA_APP_ID = get_secret("ADZUNA_APP_ID")
ADZUNA_APP_KEY = get_secret("ADZUNA_APP_KEY")
JOOBLE_API_KEY = get_secret("JOOBLE_API_KEY")
RAPIDAPI_KEY = get_secret("RAPIDAPI_KEY")

# -------------------------------------------------------------
# GÉOLOCALISATION SUD & OCCITANIE
# -------------------------------------------------------------
ZONES_SUD = {
    "Cournonsec / Montpellier (34)": {"lat": 43.5483, "lon": 3.7042, "code_insee": "34087", "dept": "34"},
    "Montpellier Métropole (34)": {"lat": 43.6108, "lon": 3.8767, "code_insee": "34172", "dept": "34"},
    "Sète & Bassin de Thau (34)": {"lat": 43.4079, "lon": 3.6928, "code_insee": "34301", "dept": "34"},
    "Béziers Méditerranée (34)": {"lat": 43.3442, "lon": 3.2158, "code_insee": "34032", "dept": "34"},
    "Nîmes & Gard (30)": {"lat": 43.8367, "lon": 4.3601, "code_insee": "30189", "dept": "30"},
    "Narbonne / Aude (11)": {"lat": 43.1836, "lon": 3.0042, "code_insee": "11262", "dept": "11"},
    "Perpignan (66)": {"lat": 42.6986, "lon": 2.8956, "code_insee": "66136", "dept": "66"},
    "Toulouse Métropole (31)": {"lat": 43.6047, "lon": 1.4442, "code_insee": "31555", "dept": "31"},
    "Avignon / Provence (84)": {"lat": 43.9493, "lon": 4.8055, "code_insee": "84007", "dept": "84"},
    "Toute l'Occitanie": {"lat": 43.6108, "lon": 3.8767, "code_insee": "", "dept": "34,30,11,66,31"}
}

# -------------------------------------------------------------
# EXTENSION DES MOTS-CLÉS (SYNONYMES EXPERTS HSE/QSE...)
# -------------------------------------------------------------
SYNONYMES_METIERS = {
    "hse": ["HSE", "QSE", "SSE", "hygiene securite environnement", "animateur securite", "responsable securite", "coordinateur securite", "prevention des risques"],
    "qse": ["QSE", "HSE", "qualite securite environnement", "animateur qse", "responsable qse", "auditeur qualite"],
    "rh": ["ressources humaines", "charge de recrutement", "gestionnaire de paie", "assistant rh"],
    "dev": ["developpeur", "ingenieur logiciel", "fullstack", "python", "informatique"],
    "btp": ["conducteur de travaux", "chef de chantier", "ingenieur btp", "coordonnateur sps"]
}

def enrichir_mots_cles(query):
    q_clean = query.strip().lower()
    for key, syns in SYNONYMES_METIERS.items():
        if key in q_clean.split() or q_clean == key:
            return syns
    return [query] if query else [""]

# -------------------------------------------------------------
# CONNECTEURS D'APIS
# -------------------------------------------------------------
@st.cache_data(ttl=900)
def get_ft_token(client_id, client_secret):
    if not client_id or not client_secret:
        return None
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_key?realm=%2Fpartenaire"
    try:
        r = requests.post(url, headers={"Content-Type": "application/x-www-form-urlencoded"},
                          data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": "api_offresdemploiv2 o2dsoffre"},
                          timeout=8)
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None

def fetch_france_travail(query_list, zone_info, distance_km):
    token = get_ft_token(FT_CLIENT_ID, FT_CLIENT_SECRET)
    if not token:
        return []
    offres = []
    base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for q in query_list[:3]:
        params = {"motsCles": q, "range": "0-49"}
        if zone_info.get("code_insee"):
            params["commune"] = zone_info["code_insee"]
            params["distance"] = min(distance_km, 100)
        elif zone_info.get("dept"):
            params["departement"] = zone_info["dept"].split(",")[0]
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=8)
            if resp.status_code == 200:
                for item in resp.json().get("resultats", []):
                    offres.append({
                        "source": "France Travail",
                        "id": f"FT_{item.get('id')}",
                        "titre": item.get("intitule", "Poste sans titre"),
                        "entreprise": item.get("entreprise", {}).get("nom", "Confidentiel"),
                        "ville": item.get("lieuTravail", {}).get("libelle", "Sud"),
                        "type_contrat": item.get("typeContratLibelle", item.get("typeContrat", "Non spécifié")),
                        "salaire": item.get("salaire", {}).get("libelle", "Non spécifié"),
                        "description": item.get("description", "")[:240] + "...",
                        "url": item.get("origineOffre", {}).get("urlOrigine", f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id')}"),
                        "date": item.get("dateCreation", "")[:10]
                    })
        except Exception:
            continue
    return offres

def fetch_adzuna(query_list, zone_name, distance_km):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    offres = []
    base_url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
    q_str = " OR ".join([f'"{q}"' if " " in q else q for q in query_list[:3]])
    params = {
        "app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY,
        "what": q_str if q_str else "emploi", "where": zone_name.split()[0],
        "distance": distance_km, "results_per_page": 40, "content-type": "application/json"
    }
    try:
        r = requests.get(base_url, params=params, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("results", []):
                offres.append({
                    "source": "Adzuna",
                    "id": f"ADZ_{item.get('id')}",
                    "titre": item.get("title", "").replace("<strong>", "").replace("</strong>", ""),
                    "entreprise": item.get("company", {}).get("display_name", "Entreprise"),
                    "ville": item.get("location", {}).get("display_name", "Occitanie"),
                    "type_contrat": item.get("contract_type", "Non spécifié"),
                    "salaire": f"{int(item.get('salary_min', 0))} € - {int(item.get('salary_max', 0))} €" if item.get('salary_min') else "Non spécifié",
                    "description": item.get("description", "")[:240] + "...",
                    "url": item.get("redirect_url", "#"),
                    "date": item.get("created", "")[:10]
                })
    except Exception:
        pass
    return offres

def fetch_jooble(query_list, zone_name, distance_km):
    if not JOOBLE_API_KEY:
        return []
    offres = []
    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    keywords = " ".join(query_list[:2])
    payload = {"keywords": keywords if keywords else "recrutement", "location": zone_name.split()[0], "radius": str(distance_km), "page": 1}
    try:
        r = requests.post(url, json=payload, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("jobs", []):
                offres.append({
                    "source": "Jooble",
                    "id": f"JB_{item.get('id')}",
                    "titre": item.get("title", ""),
                    "entreprise": item.get("company", "Entreprise"),
                    "ville": item.get("location", "Sud"),
                    "type_contrat": item.get("type", "Non spécifié"),
                    "salaire": item.get("salary", "Non spécifié") or "Non spécifié",
                    "description": item.get("snippet", "")[:240].replace("<b>", "").replace("</b>", "") + "...",
                    "url": item.get("link", "#"),
                    "date": item.get("updated", "")[:10]
                })
    except Exception:
        pass
    return offres

def fetch_jsearch(query_list, zone_name, distance_km):
    if not RAPIDAPI_KEY:
        return []
    offres = []
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "jsearch.p.rapidapi.com"}
    params = {"query": f"{query_list[0]} in {zone_name.split()[0]}, France", "page": "1", "num_pages": "1", "date_posted": "all", "distance": str(distance_km)}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=9)
        if r.status_code == 200:
            for item in r.json().get("data", []):
                offres.append({
                    "source": "Indeed/LinkedIn",
                    "id": f"JS_{item.get('job_id')}",
                    "titre": item.get("job_title", ""),
                    "entreprise": item.get("employer_name", "Recruteur"),
                    "ville": f"{item.get('job_city', '')} ({item.get('job_state', 'Occitanie')})",
                    "type_contrat": item.get("job_employment_type", "Non spécifié"),
                    "salaire": f"{item.get('job_min_salary', '')} - {item.get('job_max_salary', '')} {item.get('job_salary_currency', 'EUR')}" if item.get('job_min_salary') else "Non spécifié",
                    "description": item.get("job_description", "")[:240] + "...",
                    "url": item.get("job_apply_link", item.get("job_google_link", "#")),
                    "date": (item.get("job_posted_at_datetime_utc", "") or "")[:10]
                })
    except Exception:
        pass
    return offres

# -------------------------------------------------------------
# INTERFACE MOBILE (HEADER & RECHERCHE RAPIDE DIRECTE)
# -------------------------------------------------------------
st.title("🎯 JobRadar Mobile")

# Barre de recherche principale sur mobile (directement accessible sans menu latéral)
metier_saisi = st.text_input("🔍 Métier / Mots-clés :", value="HSE", placeholder="ex: HSE, QSE, RH, Logistique...")

col1, col2 = st.columns([3, 2])
with col1:
    choix_zone = st.selectbox("📍 Zone :", options=list(ZONES_SUD.keys()), index=0)
with col2:
    rayon_km = st.select_slider("Rayon :", options=[10, 20, 35, 50, 80, 100], value=35)

zone_data = ZONES_SUD[choix_zone]

# Panneau dépliable pour les options avancées sur mobile
with st.expander("⚙️ Plus de filtres (Contrat, Sources...)"):
    type_contrat = st.multiselect("Contrat :", ["CDI", "CDD", "Intérim", "Alternance"], default=[])
    sources_actives = st.multiselect("Moteurs actifs :", ["France Travail", "Adzuna", "Jooble", "Indeed/LinkedIn"],
                                     default=["France Travail", "Adzuna", "Jooble", "Indeed/LinkedIn"])

# Bouton de recherche tactile bien large
btn_lancer = st.button("🚀 Trouver les offres d'emploi", type="primary", use_container_width=True)

# Synonymes automatiques
termes_recherche = enrichir_mots_cles(metier_saisi)
if len(termes_recherche) > 1:
    st.info(f"✨ **Mode expert activé ({metier_saisi})** : recherche automatique incluant *{', '.join(termes_recherche[:3])}*")

# --- EXECUTION DE LA RECHERCHE ---
if btn_lancer or "resultats" not in st.session_state:
    with st.spinner("Recherche des opportunités en direct..."):
        all_jobs = []
        if "France Travail" in sources_actives:
            all_jobs.extend(fetch_france_travail(termes_recherche, zone_data, rayon_km))
        if "Adzuna" in sources_actives:
            all_jobs.extend(fetch_adzuna(termes_recherche, choix_zone, rayon_km))
        if "Jooble" in sources_actives:
            all_jobs.extend(fetch_jooble(termes_recherche, choix_zone, rayon_km))
        if "Indeed/LinkedIn" in sources_actives:
            all_jobs.extend(fetch_jsearch(termes_recherche, choix_zone, rayon_km))
        
        # Dédoublonnage
        uniques = {}
        for j in all_jobs:
            cle = f"{j['titre'].lower().strip()}_{j['entreprise'].lower().strip()}"
            if cle not in uniques:
                uniques[cle] = j
        st.session_state["resultats"] = list(uniques.values())

resultats = st.session_state.get("resultats", [])

# Compteur d'offres
st.markdown(f"**{len(resultats)} opportunités trouvées** autour de `{choix_zone.split()[0]}` ({rayon_km} km)")

# Onglets optimisés navigation smartphone
tab_offres, tab_carte = st.tabs(["📋 Offres", "🗺️ Carte"])

with tab_offres:
    if not resultats:
        st.warning("Aucune offre trouvée avec ces filtres. Essayez d'augmenter le rayon à 50 km.")
    else:
        for job in resultats:
            st.markdown(f"""
            <div class="job-card">
                <div class="job-title">{job['titre']}</div>
                <div class="job-company">🏢 {job['entreprise']}</div>
                <div class="job-badges">
                    <span class="badge badge-loc">📍 {job['ville']}</span>
                    <span class="badge badge-contract">📄 {job['type_contrat']}</span>
                    <span class="badge badge-salary">💰 {job['salaire']}</span>
                    <span class="badge badge-source">{job['source']}</span>
                </div>
                <div class="job-desc">{job['description']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("👉 Voir & Postuler", job["url"], use_container_width=True)
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

with tab_carte:
    m = folium.Map(location=[zone_data["lat"], zone_data["lon"]], zoom_start=9)
    folium.Circle(
        location=[zone_data["lat"], zone_data["lon"]],
        radius=rayon_km * 1000,
        color="#2563eb",
        fill=True,
        fill_opacity=0.15
    ).add_to(m)
    folium.Marker(
        [zone_data["lat"], zone_data["lon"]],
        popup=f"Zone : {choix_zone}",
        icon=folium.Icon(color="blue", icon="bullseye", prefix="fa")
    ).add_to(m)
    st_folium(m, width="100%", height=420)
