clean_app_code = '''import os
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv

load_dotenv()

# Configuration Streamlit Responsive (PC & Mobile)
st.set_page_config(
    page_title="JobRadar Sud & Occitanie",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# STYLE ÉPURÉ & RESPONSIVE
# -------------------------------------------------------------
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    .job-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
    }
    .job-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
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
        margin-bottom: 10px;
    }
    .stButton > button, .stLinkButton > a {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# RÉCUPÉRATION DES SECRETS
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
# RÉFÉRENTIEL GÉOGRAPHIQUE DU SUD
# -------------------------------------------------------------
ZONES_SUD = {
    "Cournonsec / Montpellier Ouest (34)": {"lat": 43.5483, "lon": 3.7042, "code_insee": "34087", "dept": "34", "name": "Cournonsec"},
    "Montpellier Métropole (34)": {"lat": 43.6108, "lon": 3.8767, "code_insee": "34172", "dept": "34", "name": "Montpellier"},
    "Sète & Bassin de Thau (34)": {"lat": 43.4079, "lon": 3.6928, "code_insee": "34301", "dept": "34", "name": "Sete"},
    "Béziers Méditerranée (34)": {"lat": 43.3442, "lon": 3.2158, "code_insee": "34032", "dept": "34", "name": "Beziers"},
    "Nîmes & Gard (30)": {"lat": 43.8367, "lon": 4.3601, "code_insee": "30189", "dept": "30", "name": "Nimes"},
    "Narbonne / Aude (11)": {"lat": 43.1836, "lon": 3.0042, "code_insee": "11262", "dept": "11", "name": "Narbonne"},
    "Perpignan / Roussillon (66)": {"lat": 42.6986, "lon": 2.8956, "code_insee": "66136", "dept": "66", "name": "Perpignan"},
    "Toulouse & Haute-Garonne (31)": {"lat": 43.6047, "lon": 1.4442, "code_insee": "31555", "dept": "31", "name": "Toulouse"},
    "Avignon / Provence (84)": {"lat": 43.9493, "lon": 4.8055, "code_insee": "84007", "dept": "84", "name": "Avignon"},
    "Toute l'Occitanie (Tous départements)": {"lat": 43.6108, "lon": 3.8767, "code_insee": "", "dept": "34,30,11,66,31,12,81,82,46,32,65,09,48", "name": "Occitanie"}
}

# -------------------------------------------------------------
# APIS DE RECHERCHE DIRECTE (RECHERCHE BRUTE SANS MODIFICATION)
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

def fetch_france_travail(keyword, zone_info, distance_km):
    token = get_ft_token(FT_CLIENT_ID, FT_CLIENT_SECRET)
    if not token:
        return []
    offres = []
    base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    params = {"range": "0-49"}
    if keyword.strip():
        params["motsCles"] = keyword.strip()
        
    if zone_info.get("code_insee"):
        params["commune"] = zone_info["code_insee"]
        params["distance"] = min(distance_km, 100)
    elif zone_info.get("dept"):
        # Si multi-départements ou Occitanie
        params["departement"] = zone_info["dept"].split(",")[0]
        
    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=8)
        if resp.status_code in [200, 206]:
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
        pass
    return offres

def fetch_adzuna(keyword, zone_name, distance_km):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    offres = []
    base_url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword.strip() if keyword.strip() else "emploi",
        "where": zone_name,
        "distance": distance_km,
        "results_per_page": 50,
        "content-type": "application/json"
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
                    "ville": item.get("location", {}).get("display_name", "Sud"),
                    "type_contrat": item.get("contract_type", "Non spécifié"),
                    "salaire": f"{int(item.get('salary_min', 0))} € - {int(item.get('salary_max', 0))} €" if item.get('salary_min') else "Non spécifié",
                    "description": item.get("description", "")[:240] + "...",
                    "url": item.get("redirect_url", "#"),
                    "date": item.get("created", "")[:10]
                })
    except Exception:
        pass
    return offres

def fetch_jooble(keyword, zone_name, distance_km):
    if not JOOBLE_API_KEY:
        return []
    offres = []
    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    payload = {
        "keywords": keyword.strip() if keyword.strip() else "recrutement",
        "location": zone_name,
        "radius": str(distance_km),
        "page": 1
    }
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

def fetch_jsearch(keyword, zone_name, distance_km):
    if not RAPIDAPI_KEY:
        return []
    offres = []
    url = "https://jsearch.p.rapidapi.com/search"
    query_text = f"{keyword.strip()} in {zone_name}, France" if keyword.strip() else f"jobs in {zone_name}, France"
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "jsearch.p.rapidapi.com"}
    params = {
        "query": query_text,
        "page": "1",
        "num_pages": "1",
        "date_posted": "all",
        "distance": str(distance_km)
    }
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
# INTERFACE PRINCIPALE DIRECTE
# -------------------------------------------------------------
st.title("🎯 JobRadar Sud")
st.caption("Recherche centralisée multi-plateformes (France Travail, Adzuna, Jooble, Indeed & LinkedIn)")

# Formulaire de recherche simple
col_kw, col_zone = st.columns([3, 2])
with col_kw:
    mot_cle = st.text_input("🔍 Mots-clés / Métier :", value="HSE", placeholder="ex: HSE, QSE, Chauffeur, Développeur...")
with col_zone:
    zone_choisie = st.selectbox("📍 Secteur géographique :", options=list(ZONES_SUD.keys()), index=0)

zone_info = ZONES_SUD[zone_choisie]

# Curseur de rayon kilométrique
col_r, col_btn = st.columns([3, 2])
with col_r:
    rayon = st.select_slider("📏 Rayon kilométrique :", options=[5, 10, 20, 35, 50, 75, 100, 150], value=35)
with col_btn:
    st.write("") # Alignement vertical
    st.write("")
    btn_chercher = st.button("🚀 Lancer la recherche", type="primary", use_container_width=True)

# -------------------------------------------------------------
# GESTION DES RÉSULTATS
# -------------------------------------------------------------
if btn_chercher or "resultats" not in st.session_state:
    with st.spinner(f"Recherche de '{mot_cle}' à {zone_info['name']} ({rayon} km)..."):
        toutes_offres = []
        
        # Interrogation directe avec le terme exact tapé
        toutes_offres.extend(fetch_france_travail(mot_cle, zone_info, rayon))
        toutes_offres.extend(fetch_adzuna(mot_cle, zone_info["name"], rayon))
        toutes_offres.extend(fetch_jooble(mot_cle, zone_info["name"], rayon))
        toutes_offres.extend(fetch_jsearch(mot_cle, zone_info["name"], rayon))
        
        # Dédoublonnage simple
        uniques = {}
        for off in toutes_offres:
            cle = f"{off['titre'].lower().strip()}_{off['entreprise'].lower().strip()}"
            if cle not in uniques:
                uniques[cle] = off
                
        st.session_state["resultats"] = list(uniques.values())

offres_affichees = st.session_state.get("resultats", [])

st.markdown(f"### **{len(offres_affichees)} offres trouvées** pour `{mot_cle}` ({zone_choisie.split()[0]} + {rayon} km)")

tab_liste, tab_map = st.tabs(["📋 Liste des offres", "🗺️ Carte interactive"])

with tab_liste:
    if not offres_affichees:
        st.warning("Aucune offre trouvée avec ce mot-clé exact dans ce périmètre. Essayez d'augmenter le rayon kilométrique ou de sélectionner 'Montpellier Métropole' ou 'Toute l'Occitanie'.")
    else:
        for job in offres_affichees:
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
            st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

with tab_map:
    st.subheader(f"Zone couverte : {zone_choisie} ({rayon} km)")
    m = folium.Map(location=[zone_info["lat"], zone_info["lon"]], zoom_start=9)
    folium.Circle(
        location=[zone_info["lat"], zone_info["lon"]],
        radius=rayon * 1000,
        color="#2563eb",
        fill=True,
        fill_opacity=0.15
    ).add_to(m)
    folium.Marker(
        [zone_info["lat"], zone_info["lon"]],
        popup=f"{zone_choisie}",
        icon=folium.Icon(color="blue", icon="bullseye", prefix="fa")
    ).add_to(m)
    st_folium(m, width="100%", height=450)
'''

with open("app.py", "w", encoding="utf-8") as f:
    f.write(clean_app_code)

print("Code sans filtrage automatique généré.")
