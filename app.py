import os
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="JobRadar - Montpellier & Cournonsec",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1400px !important;
        margin: 0 auto;
    }
    .job-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    .job-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
        border-color: #cbd5e1;
    }
    .job-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
        line-height: 1.3;
    }
    .job-company {
        font-size: 1rem;
        font-weight: 600;
        color: #2563eb;
        margin-bottom: 12px;
    }
    .job-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }
    .badge {
        font-size: 0.8rem;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    .badge-loc { background-color: #f1f5f9; color: #475569; }
    .badge-contract { background-color: #eff6ff; color: #1d4ed8; }
    .badge-salary { background-color: #ecfdf5; color: #047857; }
    .badge-source { background-color: #fef3c7; color: #b45309; }
    .job-desc {
        font-size: 0.9rem;
        color: #475569;
        line-height: 1.5;
        margin-bottom: 16px;
        flex-grow: 1;
    }
    .stButton > button, .stLinkButton > a {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s;
    }
    .stLinkButton > a:hover {
        background-color: #1d4ed8 !important;
        color: white !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

def get_secret(key, default=""):
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    val = os.getenv(key, default)
    return str(val).strip() if val else ""

FT_CLIENT_ID = get_secret("FT_CLIENT_ID")
FT_CLIENT_SECRET = get_secret("FT_CLIENT_SECRET")
ADZUNA_APP_ID = get_secret("ADZUNA_APP_ID")
ADZUNA_APP_KEY = get_secret("ADZUNA_APP_KEY")
JOOBLE_API_KEY = get_secret("JOOBLE_API_KEY")
RAPIDAPI_KEY = get_secret("RAPIDAPI_KEY")

ZONES_SUD = {
    "Cournonsec (34)": {"lat": 43.5483, "lon": 3.7042, "code_insee": "34087", "code_postal": "34660", "search_city": "Montpellier"},
    "Montpellier Métropole (34)": {"lat": 43.6108, "lon": 3.8767, "code_insee": "34172", "code_postal": "34000", "search_city": "Montpellier"}
}

SYNONYMES = {
    "hse": ["HSE", "QSE", "SSE", "sécurité environnement"],
    "rh": ["ressources humaines", "recrutement", "paie"],
    "dev": ["développeur", "fullstack", "python", "informatique"],
    "btp": ["conducteur de travaux", "chef de chantier", "btp"],
    "logistique": ["logistique", "magasinier", "préparateur"]
}

def preparer_requetes(mot_cle):
    brut = mot_cle.strip().lower()
    if not brut: return [""]
    for cle, liste_syns in SYNONYMES.items():
        if cle in brut.split() or brut == cle: return liste_syns
    return [mot_cle.strip()]

@st.cache_data(ttl=800, show_spinner=False)
def get_ft_token_optim(client_id, client_secret):
    if not client_id or not client_secret: return None
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": "api_offresdemploiv2 o2dsoffre"}
    try:
        r = requests.post(url, data=data, timeout=8)
        if r.status_code == 200:
            return r.json().get("access_token")
    except: pass
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_france_travail_optim(token, requetes, insee, lat, lon, distance_km):
    if not token: return [], "Token manquant"
    offres = []
    base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    for q in requetes[:2]:
        params = {"range": "0-99", "sort": "2"}
        if q: params["motsCles"] = q
        if insee:
            params["commune"] = insee
            params["distance"] = min(max(int(distance_km), 0), 100)
            
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=10)
            if resp.status_code in [200, 206]:
                for item in resp.json().get("resultats", []):
                    lieu = item.get("lieuTravail", {})
                    offres.append({
                        "source": "France Travail", "id": f"FT_{item.get('id')}",
                        "titre": item.get("intitule", "Poste sans titre"),
                        "entreprise": item.get("entreprise", {}).get("nom", "Confidentiel"),
                        "ville": lieu.get("libelle", "Sud"), "lat": lieu.get("latitude", lat), "lon": lieu.get("longitude", lon),
                        "type_contrat": item.get("typeContratLibelle", item.get("typeContrat", "Non spécifié")),
                        "salaire": item.get("salaire", {}).get("libelle", "Non spécifié"),
                        "description": item.get("description", "")[:200] + "...",
                        "url": item.get("origineOffre", {}).get("urlOrigine", f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id')}"),
                    })
        except: continue
    return offres, "OK"

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_adzuna_optim(requetes, search_city, lat, lon, distance_km, app_id, app_key):
    if not app_id or not app_key: return [], "Identifiants manquants"
    q_str = " OR ".join([f'"{q}"' if " " in q else q for q in requetes[:2] if q])
    params = {"app_id": app_id, "app_key": app_key, "where": search_city, "results_per_page": 40, "distance": int(distance_km)}
    if q_str: params["what"] = q_str
        
    try:
        r = requests.get("https://api.adzuna.com/v1/api/jobs/fr/search/1", params=params, timeout=8)
        if r.status_code == 200:
            return [{
                "source": "Adzuna", "id": f"ADZ_{item.get('id')}",
                "titre": item.get("title", "").replace("<strong>", "").replace("</strong>", ""),
                "entreprise": item.get("company", {}).get("display_name", "Entreprise"),
                "ville": item.get("location", {}).get("display_name", "Sud"),
                "lat": float(lat), "lon": float(lon),
                "type_contrat": item.get("contract_type", "Non spécifié"),
                "salaire": f"{int(item.get('salary_min', 0))} € -" if item.get('salary_min') else "Non spécifié",
                "description": item.get("description", "")[:200] + "...",
                "url": item.get("redirect_url", "#")
            } for item in r.json().get("results", [])], "OK"
    except: pass
    return [], "Erreur"

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_jooble_optim(requetes, search_city, lat, lon, distance_km, api_key):
    if not api_key: return [], "Clé manquante"
    keywords = " ".join([q for q in requetes[:2] if q])
    payload = {"location": search_city, "radius": str(distance_km), "page": 1, "resultOnPage": 40}
    if keywords: payload["keywords"] = keywords 
        
    try:
        r = requests.post(f"https://jooble.org/api/{api_key}", json=payload, timeout=8)
        if r.status_code == 200:
            return [{
                "source": "Jooble", "id": f"JB_{item.get('id')}",
                "titre": item.get("title", ""), "entreprise": item.get("company", "Entreprise"),
                "ville": item.get("location", "Sud"), "lat": float(lat), "lon": float(lon),
                "type_contrat": item.get("type", "Non spécifié"), "salaire": item.get("salary", "Non spécifié") or "Non spécifié",
                "description": item.get("snippet", "")[:200].replace("<b>", "").replace("</b>", "") + "...",
                "url": item.get("link", "#")
            } for item in r.json().get("jobs", [])], "OK"
    except: pass
    return [], "Erreur"

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_jsearch_optim(requetes, search_city, lat, lon, distance_km, api_key):
    if not api_key: return [], "Clé manquante"
    term = requetes[0] if (requetes and requetes[0]) else ""
    query_str = f"{term} in {search_city}, France" if term else f"jobs in {search_city}, France"
    headers = {"x-rapidapi-key": api_key, "x-rapidapi-host": "jsearch-mega.p.rapidapi.com"}
    params = {"query": query_str, "page": "1", "num_pages": "1", "radius": str(distance_km)}
    
    try:
        r = requests.get("https://jsearch-mega.p.rapidapi.com/search", headers=headers, params=params, timeout=9)
        if r.status_code == 200:
            return [{
                "source": "Indeed/LinkedIn", "id": f"JS_{item.get('job_id')}",
                "titre": item.get("job_title", ""), "entreprise": item.get("employer_name", "Recruteur"),
                "ville": item.get('job_city', search_city), "lat": item.get("job_latitude", lat), "lon": item.get("job_longitude", lon),
                "type_contrat": item.get("job_employment_type", "Non spécifié"),
                "salaire": f"{item.get('job_min_salary', '')} {item.get('job_salary_currency', 'EUR')}" if item.get('job_min_salary') else "Non spécifié",
                "description": item.get("job_description", "")[:200] + "...",
                "url": item.get("job_apply_link", item.get("job_google_link", "#"))
            } for item in r.json().get("data", [])], "OK"
    except: pass
    return [], "Erreur"

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_lba_formations_optim(mot_cle, lat, lon, radius, search_city):
    term = mot_cle if mot_cle else "emploi"
    romes = []
    
    try:
        r_met = requests.get(f"https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/metiers?title={term}", timeout=5)
        if r_met.status_code == 200 and "metiers" in r_met.json():
            for metier in r_met.json().get("metiers", []):
                romes.extend(metier.get("romes", []))
    except Exception:
        pass
        
    if not romes:
        romes = ["M1805", "M1402", "D1401", "N1303"]
        
    romes_str = ",".join(list(set(romes))[:5])
    formations = []
    
    try:
        url_form = "https://labonnealternance.apprentissage.beta.gouv.fr/api/v1/formations"
        # Forçage ultra-strict des types pour ne pas faire crasher l'API gouvernementale
        params = {
            "romes": romes_str, 
            "latitude": float(lat), 
            "longitude": float(lon), 
            "radius": int(radius), 
            "caller": "JobRadar"
        }
        r_form = requests.get(url_form, params=params, timeout=10)
        
        if r_form.status_code == 200:
            results = r_form.json().get("results", [])
            for f in results[:10]:
                org_name = f.get("company", {}).get("name", "Centre de formation certifié")
                formations.append({
                    "titre": str(f.get("title", "Titre Professionnel")).capitalize(),
                    "org": org_name,
                    "loc": f.get("place", {}).get("city", search_city),
                    "fin": "Alternance / CPF",
                    "desc": f"Formation référencée dispensée par {org_name}. Idéal pour accélérer votre transition professionnelle.",
                    "url": f"https://labonnealternance.apprentissage.beta.gouv.fr/recherche-apprentissage?&romes={romes_str}&radius={radius}&lat={lat}&lon={lon}"
                })
    except Exception:
        pass
    
    if not formations:
        formations = [
            {"titre": f"Certification d'État (Accès ciblé)", "org": "GRETA / AFPA Occitanie", "loc": search_city, "fin": "100% Éligible CPF", "desc": "Parcours complet pour valider vos acquis professionnels et décrocher un diplôme reconnu par les recruteurs du bassin d'emploi.", "url": "https://www.moncompteformation.gouv.fr/"},
            {"titre": "Validation des Acquis (VAE)", "org": "Région Occitanie", "loc": f"{search_city} (Mixte)", "fin": "Financement Intégral", "desc": "Transformez votre expérience de terrain en un diplôme officiel sans repasser par un cycle scolaire complet.", "url": "https://www.moncompteformation.gouv.fr/"}
        ]
        
    return formations

st.title("🎯 JobRadar Montpellier & Cournonsec")
st.caption("Agrégateur d'opportunités en direct optimisé pour ordinateur")

with st.container():
    col_kw, col_zone, col_r = st.columns([3, 2, 2])
    with col_kw:
        mot_cle = st.text_input("🔍 Métier / Mots-clés :", placeholder="ex: HSE, Développeur, Logistique...")
    with col_zone:
        zone_choisie = st.selectbox("📍 Secteur :", list(ZONES_SUD.keys()))
    with col_r:
        rayon = st.select_slider("📏 Rayon :", options=[5, 10, 20, 35, 50, 75], value=35)

zone_info = ZONES_SUD[zone_choisie]
contrats_choisis = st.multiselect("📄 Filtre contrats :", ["CDI", "CDD", "Intérim", "Alternance", "Temps plein", "Indépendant"])

col_btn, col_opts = st.columns([1, 3])
with col_btn:
    st.write("") 
    btn_chercher = st.button("🚀 Rechercher", type="primary", use_container_width=True)
with col_opts:
    with st.expander("⚙️ Sources de données actives"):
        sources_actives = st.multiselect("Sources :", ["France Travail", "Adzuna", "Jooble", "Indeed & LinkedIn (JSearch)"], default=["France Travail", "Adzuna", "Jooble", "Indeed & LinkedIn (JSearch)"])

if btn_chercher or "resultats" not in st.session_state:
    requetes_calculees = preparer_requetes(mot_cle)
    
    with st.spinner("Analyse du marché en cours..."):
        toutes_offres, stats = [], {}
        
        if "France Travail" in sources_actives:
            token = get_ft_token_optim(FT_CLIENT_ID, FT_CLIENT_SECRET)
            r, _ = fetch_france_travail_optim(token, requetes_calculees, zone_info.get("code_insee"), zone_info["lat"], zone_info["lon"], rayon)
            toutes_offres.extend(r); stats["France Travail"] = len(r)
            
        if "Adzuna" in sources_actives:
            r, _ = fetch_adzuna_optim(requetes_calculees, zone_info["search_city"], zone_info["lat"], zone_info["lon"], rayon, ADZUNA_APP_ID, ADZUNA_APP_KEY)
            toutes_offres.extend(r); stats["Adzuna"] = len(r)
            
        if "Jooble" in sources_actives:
            r, _ = fetch_jooble_optim(requetes_calculees, zone_info["search_city"], zone_info["lat"], zone_info["lon"], rayon, JOOBLE_API_KEY)
            toutes_offres.extend(r); stats["Jooble"] = len(r)
            
        if "Indeed & LinkedIn (JSearch)" in sources_actives:
            r, _ = fetch_jsearch_optim(requetes_calculees, zone_info["search_city"], zone_info["lat"], zone_info["lon"], rayon, RAPIDAPI_KEY)
            toutes_offres.extend(r); stats["Indeed/LinkedIn"] = len(r)
        
        uniques = {f"{o['titre']}_{o['entreprise']}": o for o in toutes_offres}.values()
        st.session_state["resultats"] = list(uniques)
        st.session_state["stats"] = stats
        st.session_state["formations"] = fetch_lba_formations_optim(mot_cle, zone_info["lat"], zone_info["lon"], rayon, zone_info["search_city"])

offres = [job for job in st.session_state.get("resultats", []) if not contrats_choisis or any(c.lower() in str(job).lower() for c in contrats_choisis)]

st.markdown(f"### **{len(offres)} opportunités trouvées**")
if st.session_state.get("stats"):
    st.caption("📊 " + " | ".join([f"**{k}**: {v}" for k, v in st.session_state["stats"].items()]))

tab_liste, tab_map, tab_cpf = st.tabs(["📋 Liste des offres", "🗺️ Carte interactive", "🎓 Formations"])

with tab_liste:
    if not offres:
        st.warning("Aucune offre pour ces critères. Élargissez le périmètre.")
    else:
        cols = st.columns(2)
        for index, job in enumerate(offres):
            col = cols[index % 2]
            with col:
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
                st.link_button("👉 Voir l'offre & Postuler", job["url"], use_container_width=True)
                st.markdown("<br>", unsafe_allow_html=True)

with tab_map:
    st.subheader(f"Cartographie du bassin d'emploi ({rayon} km)")
    m = folium.Map(location=[zone_info["lat"], zone_info["lon"]], zoom_start=10)
    folium.Circle(location=[zone_info["lat"], zone_info["lon"]], radius=rayon*1000, color="#2563eb", fill=True, fill_opacity=0.1).add_to(m)
    
    for job in offres:
        try:
            folium.Marker(
                [float(job.get("lat")), float(job.get("lon"))],
                popup=folium.Popup(f"<b>{job['titre']}</b><br>{job['entreprise']}<br><a href='{job['url']}' target='_blank'>Postuler</a>", max_width=300),
                icon=folium.Icon(color="blue", icon="briefcase", prefix="fa")
            ).add_to(m)
        except: pass
    st_folium(m, width="100%", height=600)

with tab_cpf:
    st.subheader("🎓 Formations & Titres Professionnels (La Bonne Alternance)")
    st.write("Résultats exclusifs issus du référentiel national des certifications de l'État :")
    
    formations = st.session_state.get("formations", [])
    cols_form = st.columns(2)
    for index, f in enumerate(formations):
        with cols_form[index % 2]:
            st.markdown(f"""
            <div class="job-card" style="border-left: 4px solid #10b981;">
                <div class="job-title">{f['titre']}</div>
                <div class="job-company">🎓 {f['org']}</div>
                <div class="job-badges">
                    <span class="badge badge-loc">📍 {f['loc']}</span>
                    <span class="badge badge-salary">💰 {f['fin']}</span>
                </div>
                <div class="job-desc">{f['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("👉 Découvrir le programme", f['url'], use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
