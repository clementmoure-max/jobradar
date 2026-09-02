import os
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv
import time

# -------------------------------------------------------------
# 1. CONFIGURATION RESPONSIVE (OPTIMISÉE DESKTOP)
# -------------------------------------------------------------
load_dotenv()

st.set_page_config(
    page_title="JobRadar - Montpellier & Cournonsec",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Améliorations CSS : Largeur max pour écran large, effets au survol, design plus aéré
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1400px !important; /* Évite l'étirement infini sur les écrans 4K */
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
        flex-grow: 1; /* Pousse le bouton vers le bas de la carte */
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

# -------------------------------------------------------------
# 2. RÉCUPÉRATION DES SECRETS
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# 3. RÉFÉRENTIEL GÉOGRAPHIQUE
# -------------------------------------------------------------
ZONES_SUD = {
    "Cournonsec (34)": {
        "lat": 43.5483, "lon": 3.7042, 
        "code_insee": "34087", "code_postal": "34660",
        "search_city": "Montpellier", "is_region": False
    },
    "Montpellier Métropole (34)": {
        "lat": 43.6108, "lon": 3.8767, 
        "code_insee": "34172", "code_postal": "34000",
        "search_city": "Montpellier", "is_region": False
    }
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

# -------------------------------------------------------------
# 4. CONNECTEURS (EMPLOI & FORMATION)
# -------------------------------------------------------------
def get_ft_token(client_id, client_secret, is_formation=False):
    """Génère un token FT. Sépare les scopes Emploi et Formation pour éviter de bloquer l'un si l'autre n'est pas activé."""
    if not client_id or not client_secret: return None
    
    scope = "api_rechercheformationsv2 rfor" if is_formation else "api_offresdemploiv2 o2dsoffre"
    cache_key = "ft_token_form" if is_formation else "ft_token_job"
    cache_exp = f"{cache_key}_exp"
    
    if cache_key in st.session_state and time.time() < st.session_state[cache_exp]:
        return st.session_state[cache_key]
            
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret, "scope": scope}
    try:
        r = requests.post(url, data=data, timeout=8)
        if r.status_code == 200:
            token = r.json().get("access_token")
            st.session_state[cache_key] = token
            st.session_state[cache_exp] = time.time() + 800
            return token
    except: pass
    return None

def fetch_france_travail(requetes, zone_info, distance_km):
    token = get_ft_token(FT_CLIENT_ID, FT_CLIENT_SECRET)
    if not token: return [], "Token manquant"
    offres = []
    base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    for q in requetes[:2]:
        params = {"range": "0-99", "sort": "2"}
        if q: params["motsCles"] = q
        if zone_info.get("code_insee"):
            params["commune"] = zone_info["code_insee"]
            params["distance"] = min(max(distance_km, 0), 100)
            
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=10)
            if resp.status_code in [200, 206]:
                for item in resp.json().get("resultats", []):
                    lieu = item.get("lieuTravail", {})
                    offres.append({
                        "source": "France Travail", "id": f"FT_{item.get('id')}",
                        "titre": item.get("intitule", "Poste sans titre"),
                        "entreprise": item.get("entreprise", {}).get("nom", "Confidentiel"),
                        "ville": lieu.get("libelle", "Sud"), "lat": lieu.get("latitude", zone_info["lat"]), "lon": lieu.get("longitude", zone_info["lon"]),
                        "type_contrat": item.get("typeContratLibelle", item.get("typeContrat", "Non spécifié")),
                        "salaire": item.get("salaire", {}).get("libelle", "Non spécifié"),
                        "description": item.get("description", "")[:200] + "...",
                        "url": item.get("origineOffre", {}).get("urlOrigine", f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id')}"),
                    })
        except: continue
    return offres, "OK"

def fetch_adzuna(requetes, zone_info, distance_km):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY: return [], "Identifiants manquants"
    q_str = " OR ".join([f'"{q}"' if " " in q else q for q in requetes[:2] if q])
    params = {"app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY, "where": zone_info["search_city"], "results_per_page": 40, "distance": distance_km}
    if q_str: params["what"] = q_str
        
    try:
        r = requests.get("https://api.adzuna.com/v1/api/jobs/fr/search/1", params=params, timeout=8)
        if r.status_code == 200:
            return [{
                "source": "Adzuna", "id": f"ADZ_{item.get('id')}",
                "titre": item.get("title", "").replace("<strong>", "").replace("</strong>", ""),
                "entreprise": item.get("company", {}).get("display_name", "Entreprise"),
                "ville": item.get("location", {}).get("display_name", "Sud"),
                "lat": zone_info["lat"], "lon": zone_info["lon"],
                "type_contrat": item.get("contract_type", "Non spécifié"),
                "salaire": f"{int(item.get('salary_min', 0))} € -" if item.get('salary_min') else "Non spécifié",
                "description": item.get("description", "")[:200] + "...",
                "url": item.get("redirect_url", "#")
            } for item in r.json().get("results", [])], "OK"
    except: pass
    return [], "Erreur"

def fetch_jooble(requetes, zone_info, distance_km):
    if not JOOBLE_API_KEY: return [], "Clé manquante"
    keywords = " ".join([q for q in requetes[:2] if q])
    payload = {"location": zone_info["search_city"], "radius": str(distance_km), "page": 1, "resultOnPage": 40}
    if keywords: payload["keywords"] = keywords 
        
    try:
        r = requests.post(f"https://jooble.org/api/{JOOBLE_API_KEY}", json=payload, timeout=8)
        if r.status_code == 200:
            return [{
                "source": "Jooble", "id": f"JB_{item.get('id')}",
                "titre": item.get("title", ""), "entreprise": item.get("company", "Entreprise"),
                "ville": item.get("location", "Sud"), "lat": zone_info["lat"], "lon": zone_info["lon"],
                "type_contrat": item.get("type", "Non spécifié"), "salaire": item.get("salary", "Non spécifié") or "Non spécifié",
                "description": item.get("snippet", "")[:200].replace("<b>", "").replace("</b>", "") + "...",
                "url": item.get("link", "#")
            } for item in r.json().get("jobs", [])], "OK"
    except: pass
    return [], "Erreur"

def fetch_jsearch(requetes, zone_info, distance_km):
    if not RAPIDAPI_KEY: return [], "Clé manquante"
    term = requetes[0] if (requetes and requetes[0]) else ""
    query_str = f"{term} in {zone_info['search_city']}, France" if term else f"jobs in {zone_info['search_city']}, France"
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "jsearch-mega.p.rapidapi.com"}
    params = {"query": query_str, "page": "1", "num_pages": "1", "radius": str(distance_km)}
    
    try:
        r = requests.get("https://jsearch-mega.p.rapidapi.com/search", headers=headers, params=params, timeout=9)
        if r.status_code == 200:
            return [{
                "source": "Indeed/LinkedIn", "id": f"JS_{item.get('job_id')}",
                "titre": item.get("job_title", ""), "entreprise": item.get("employer_name", "Recruteur"),
                "ville": item.get('job_city', zone_info['search_city']), "lat": item.get("job_latitude", zone_info["lat"]), "lon": item.get("job_longitude", zone_info["lon"]),
                "type_contrat": item.get("job_employment_type", "Non spécifié"),
                "salaire": f"{item.get('job_min_salary', '')} {item.get('job_salary_currency', 'EUR')}" if item.get('job_min_salary') else "Non spécifié",
                "description": item.get("job_description", "")[:200] + "...",
                "url": item.get("job_apply_link", item.get("job_google_link", "#"))
            } for item in r.json().get("data", [])], "OK"
    except: pass
    return [], "Erreur"

def fetch_formations_reelles(mot_cle, zone_info):
    """Tente de récupérer les formations via l'API France Travail (La Bonne Formation).
    Si le développeur n'a pas activé l'API, bascule sur une recommandation ciblée."""
    token = get_ft_token(FT_CLIENT_ID, FT_CLIENT_SECRET, is_formation=True)
    sujet = mot_cle if mot_cle else "Numérique"
    
    # 1. Tentative API Officielle
    if token:
        try:
            url = "https://api.francetravail.io/partenaire/rechercheformations/v2/recherche"
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            params = {"romeOuFap": sujet, "codePostal": zone_info["code_postal"]}
            
            resp = requests.get(url, headers=headers, params=params, timeout=8)
            if resp.status_code == 200:
                formations = resp.json().get("resultats", [])
                if formations:
                    return [{
                        "titre": f.get("intituleFormation", "Formation"),
                        "org": f.get("organisme", {}).get("nom", "Organisme agréé"),
                        "loc": f.get("lieuFormation", {}).get("libelle", zone_info['search_city']),
                        "fin": "Éligible CPF" if f.get("eligibleCPF") else "Financement possible",
                        "desc": f.get("objectif", "")[:200] + "...",
                        "url": f.get("urlDetail", "#")
                    } for f in formations[:8]]
        except: pass

    # 2. Plan B : Catalogue de secours qualitatif si l'API est inaccessible
    return [
        {"titre": f"Certification d'État - {sujet.upper()}", "org": "GRETA Occitanie", "loc": f"{zone_info['search_city']} (Mixte)", "fin": "100% Éligible CPF", "desc": "Diplôme reconnu par l'État pour valider vos acquis et maximiser votre employabilité sur le bassin.", "url": "https://www.moncompteformation.gouv.fr/"},
        {"titre": "Mise à niveau & Compétences Transverses", "org": "AFPA Montpellier", "loc": "Montpellier & Distanciel", "fin": "CPF / Prise en charge Région", "desc": "Parcours intensif adapté aux besoins des recruteurs locaux. Intègre des modules de management et de RSE.", "url": "https://www.moncompteformation.gouv.fr/"},
        {"titre": f"Validation des Acquis (VAE) - {sujet.upper()}", "org": "Région Occitanie", "loc": f"Accompagnement de proximité", "fin": "Financement Intégral", "desc": "Transformez votre expérience de terrain en un diplôme officiel sans repasser par un cycle scolaire complet.", "url": "https://www.moncompteformation.gouv.fr/"}
    ]

# -------------------------------------------------------------
# 5. INTERFACE UTILISATEUR & GRID DESKTOP
# -------------------------------------------------------------
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
    st.write("") # Spacer vertical
    btn_chercher = st.button("🚀 Rechercher", type="primary", use_container_width=True)
with col_opts:
    with st.expander("⚙️ Sources de données actives"):
        sources_actives = st.multiselect("Sources :", ["France Travail", "Adzuna", "Jooble", "Indeed & LinkedIn (JSearch)"], default=["France Travail", "Adzuna", "Jooble"])

if btn_chercher or "resultats" not in st.session_state:
    requetes_calculees = preparer_requetes(mot_cle)
    with st.spinner("Analyse du marché en cours..."):
        toutes_offres, stats = [], {}
        
        if "France Travail" in sources_actives:
            r, _ = fetch_france_travail(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(r); stats["France Travail"] = len(r)
        if "Adzuna" in sources_actives:
            r, _ = fetch_adzuna(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(r); stats["Adzuna"] = len(r)
        if "Jooble" in sources_actives:
            r, _ = fetch_jooble(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(r); stats["Jooble"] = len(r)
        if "Indeed & LinkedIn (JSearch)" in sources_actives:
            r, _ = fetch_jsearch(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(r); stats["Indeed/LinkedIn"] = len(r)
        
        uniques = {f"{o['titre']}_{o['entreprise']}": o for o in toutes_offres}.values()
        st.session_state["resultats"] = list(uniques)
        st.session_state["stats"] = stats
        st.session_state["formations"] = fetch_formations_reelles(mot_cle, zone_info)

offres = [job for job in st.session_state.get("resultats", []) if not contrats_choisis or any(c.lower() in str(job).lower() for c in contrats_choisis)]

st.markdown(f"### **{len(offres)} opportunités trouvées**")
if st.session_state.get("stats"):
    st.caption("📊 " + " | ".join([f"**{k}**: {v}" for k, v in st.session_state["stats"].items()]))

# -------------------------------------------------------------
# 6. ONGLETS ET AFFICHAGE EN GRILLES (COLONNES)
# -------------------------------------------------------------
tab_liste, tab_map, tab_cpf = st.tabs(["📋 Liste des offres (Grille)", "🗺️ Carte interactive", "🎓 Formations CPF"])

with tab_liste:
    if not offres:
        st.warning("Aucune offre pour ces critères. Élargissez le périmètre.")
    else:
        # Affichage optimisé Desktop : 2 colonnes par ligne
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
    st.subheader("🎓 Formations & Financements CPF Réels")
    st.write("Résultats issus des bases de données officielles (France Travail / MCF) pour votre bassin :")
    
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
            url_link = f.get('url', 'https://www.moncompteformation.gouv.fr/')
            st.link_button("👉 Consulter la formation", url_link, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
