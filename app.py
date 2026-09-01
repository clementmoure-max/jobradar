import os
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv
import time

# -------------------------------------------------------------
# 1. CONFIGURATION RESPONSIVE
# -------------------------------------------------------------
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
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
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
        line-height: 1.45;
        margin-bottom: 12px;
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
# 2. RÉCUPÉRATION DES SECRETS (BLINDÉ LOCAL & CLOUD)
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
# 3. RÉFÉRENTIEL GÉOGRAPHIQUE RESTREINT
# -------------------------------------------------------------
ZONES_SUD = {
    "Cournonsec (34)": {
        "lat": 43.5483, "lon": 3.7042, 
        "code_insee": "34087",
        "dept": "34", "region_ft": "76",
        "search_city": "Montpellier",
        "is_region": False
    },
    "Montpellier Métropole (34)": {
        "lat": 43.6108, "lon": 3.8767, 
        "code_insee": "34172", 
        "dept": "34", "region_ft": "76",
        "search_city": "Montpellier", 
        "is_region": False
    }
}

# -------------------------------------------------------------
# 4. ÉLARGISSEMENT DES TERMES
# -------------------------------------------------------------
SYNONYMES = {
    "hse": ["HSE", "QSE", "SSE", "sécurité environnement", "prévention des risques", "animateur sécurité"],
    "qse": ["QSE", "HSE", "qualité sécurité environnement", "coordinateur qse"],
    "sse": ["SSE", "HSE", "santé sécurité environnement"],
    "rh": ["ressources humaines", "recrutement", "gestionnaire de paie", "assistant rh"],
    "dev": ["développeur", "fullstack", "frontend", "backend", "python", "informatique"],
    "btp": ["conducteur de travaux", "chef de chantier", "ingénieur btp", "coordonnateur sps"],
    "logistique": ["logistique", "magasinier", "préparateur de commandes", "gestionnaire de stocks"]
}

def preparer_requetes(mot_cle):
    brut = mot_cle.strip().lower()
    if not brut:
        return [""]
    for cle, liste_syns in SYNONYMES.items():
        if cle in brut.split() or brut == cle:
            return liste_syns
    return [mot_cle.strip()]

# -------------------------------------------------------------
# 5. CONNECTEUR FRANCE TRAVAIL (AVEC DIAGNOSTIC)
# -------------------------------------------------------------
def get_ft_token(client_id, client_secret):
    if not client_id or not client_secret:
        return None, "Identifiants FT manquants dans les secrets."
    
    if "ft_token" in st.session_state and "ft_token_exp" in st.session_state:
        if time.time() < st.session_state["ft_token_exp"]:
            return st.session_state["ft_token"], "OK"
            
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "api_offresdemploiv2 o2dsoffre"
    }
    try:
        r = requests.post(url, headers=headers, data=data, timeout=12)
        if r.status_code == 200:
            token = r.json().get("access_token")
            st.session_state["ft_token"] = token
            st.session_state["ft_token_exp"] = time.time() + 800
            return token, "OK"
        return None, f"Erreur Auth {r.status_code} : {r.text}"
    except requests.exceptions.Timeout:
        return None, "Serveur FT injoignable (Timeout)"
    except Exception as e:
        return None, str(e)

def fetch_france_travail(requetes, zone_info, distance_km):
    token, statut_token = get_ft_token(FT_CLIENT_ID, FT_CLIENT_SECRET)
    if not token:
        return [], statut_token
    
    offres = []
    base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    for q in requetes[:3]:
        params = {"range": "0-49", "sort": "2"}
        params["motsCles"] = q if q else "emploi" 
            
        if zone_info.get("code_insee"):
            params["commune"] = zone_info["code_insee"]
            params["distance"] = min(max(distance_km, 10), 100)
            
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=12)
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
            else:
                return offres, f"Erreur Recherche {resp.status_code} : {resp.text}"
        except Exception as e:
            return offres, f"Erreur de connexion : {str(e)}"
    return offres, "OK"

# -------------------------------------------------------------
# 6. CONNECTEURS EXTERNES (ADZUNA, JOOBLE, JSEARCH-MEGA)
# -------------------------------------------------------------
def fetch_adzuna(requetes, zone_info, distance_km):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY: return [], "Identifiants Adzuna manquants"
    offres = []
    base_url = "https://api.adzuna.com/v1/api/jobs/fr/search/1"
    q_str = " OR ".join([f'"{q}"' if " " in q else q for q in requetes[:3] if q])
    
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": q_str if q_str else "emploi",
        "where": zone_info["search_city"],
        "results_per_page": 50,
        "distance": distance_km,
        "content-type": "application/json"
    }
        
    try:
        r = requests.get(base_url, params=params, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("results", []):
                offres.append({"source": "Adzuna", "id": f"ADZ_{item.get('id')}", "titre": item.get("title", "").replace("<strong>", "").replace("</strong>", ""), "entreprise": item.get("company", {}).get("display_name", "Entreprise"), "ville": item.get("location", {}).get("display_name", "Sud"), "type_contrat": item.get("contract_type", "Non spécifié"), "salaire": f"{int(item.get('salary_min', 0))} € - {int(item.get('salary_max', 0))} €" if item.get('salary_min') else "Non spécifié", "description": item.get("description", "")[:240] + "...", "url": item.get("redirect_url", "#"), "date": item.get("created", "")[:10]})
            return offres, "OK"
        else:
            return [], f"Erreur {r.status_code} : {r.text}"
    except Exception as e: 
        return [], str(e)

def fetch_jooble(requetes, zone_info, distance_km):
    if not JOOBLE_API_KEY: return [], "Clé API Jooble manquante"
    offres = []
    url = f"https://jooble.org/api/{JOOBLE_API_KEY}"
    keywords = " ".join([q for q in requetes[:2] if q])
    
    payload = {
        "location": zone_info["search_city"],
        "radius": str(distance_km),
        "page": 1,
        "keywords": keywords if keywords else "emploi" 
    }
        
    try:
        r = requests.post(url, json=payload, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("jobs", []):
                offres.append({"source": "Jooble", "id": f"JB_{item.get('id')}", "titre": item.get("title", ""), "entreprise": item.get("company", "Entreprise"), "ville": item.get("location", "Sud"), "type_contrat": item.get("type", "Non spécifié"), "salaire": item.get("salary", "Non spécifié") or "Non spécifié", "description": item.get("snippet", "")[:240].replace("<b>", "").replace("</b>", "") + "...", "url": item.get("link", "#"), "date": item.get("updated", "")[:10]})
            return offres, "OK"
        else:
            return [], f"Erreur {r.status_code} : {r.text[:100]}"
    except Exception as e: 
        return [], str(e)

def fetch_jsearch(requetes, zone_info, distance_km):
    if not RAPIDAPI_KEY: return [], "Clé JSearch/RapidAPI manquante"
    offres = []
    url = "https://jsearch-mega.p.rapidapi.com/search"
    term = requetes[0] if (requetes and requetes[0]) else "emploi"
    query_str = f"{term} in {zone_info['search_city']}, France"
    
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "jsearch-mega.p.rapidapi.com"}
    params = {"query": query_str, "page": "1", "num_pages": "1", "distance": str(distance_km), "date_posted": "all"}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=9)
        if r.status_code == 200:
            for item in r.json().get("data", []):
                offres.append({"source": "Indeed/LinkedIn", "id": f"JS_{item.get('job_id')}", "titre": item.get("job_title", ""), "entreprise": item.get("employer_name", "Recruteur"), "ville": f"{item.get('job_city', '')} ({item.get('job_state', 'Occitanie')})", "type_contrat": item.get("job_employment_type", "Non spécifié"), "salaire": f"{item.get('job_min_salary', '')} - {item.get('job_max_salary', '')} {item.get('job_salary_currency', 'EUR')}" if item.get('job_min_salary') else "Non spécifié", "description": item.get("job_description", "")[:240] + "...", "url": item.get("job_apply_link", item.get("job_google_link", "#")), "date": (item.get("job_posted_at_datetime_utc", "") or "")[:10]})
            return offres, "OK"
        else:
            return [], f"Erreur {r.status_code} : {r.text[:100]}"
    except Exception as e: 
        return [], str(e)

# -------------------------------------------------------------
# 7. SCANNER DE CONTRATS
# -------------------------------------------------------------
def correspond_contrat(job, contrats_selectionnes):
    if not contrats_selectionnes: return True
    texte_total = f"{job.get('type_contrat', '')} {job.get('titre', '')} {job.get('description', '')}".lower()
    for c in contrats_selectionnes:
        c_low = c.lower()
        if "cdi" in c_low and "cdi" in texte_total: return True
        if "cdd" in c_low and "cdd" in texte_total: return True
        if "intérim" in c_low and any(k in texte_total for k in ["intérim", "interim", "mission temporaire"]): return True
        if "alternance" in c_low and any(k in texte_total for k in ["alternance", "stage", "apprentissage", "contrat pro"]): return True
        if "plein" in c_low and any(k in texte_total for k in ["temps plein", "plein", "35h", "39h"]): return True
        if "partiel" in c_low and "partiel" in texte_total: return True
        if "indépendant" in c_low and any(k in texte_total for k in ["indépendant", "independant", "freelance"]): return True
    return False

# -------------------------------------------------------------
# 8. INTERFACE UTILISATEUR
# -------------------------------------------------------------
st.title("🎯 JobRadar Montpellier & Cournonsec")
st.caption("Agrégateur d'opportunités en direct : France Travail, Adzuna, Jooble, Indeed & LinkedIn")

col_kw, col_zone = st.columns([3, 2])
with col_kw:
    mot_cle = st.text_input("🔍 Métier / Mots-clés :", value="", placeholder="ex: HSE, QSE, Chauffeur, Développeur, Logistique...")
with col_zone:
    zone_choisie = st.selectbox("📍 Secteur géographique :", options=list(ZONES_SUD.keys()), index=0)

zone_info = ZONES_SUD[zone_choisie]

col_r, col_c = st.columns([2, 3])
with col_r:
    rayon = st.select_slider("📏 Rayon kilométrique :", options=[5, 10, 20, 35, 50, 75, 100], value=35)
        
with col_c:
    contrats_choisis = st.multiselect("📄 Filtrer par contrat :", options=["CDI", "CDD", "Intérim", "Alternance / Stage", "Temps plein", "Temps partiel", "Indépendant"], default=[])

with st.expander("⚙️ Plateformes interrogées"):
    sources_actives = st.multiselect("Sources actives :", options=["France Travail", "Adzuna", "Jooble", "Indeed & LinkedIn (JSearch)"], default=["France Travail", "Adzuna", "Jooble", "Indeed & LinkedIn (JSearch)"])

btn_chercher = st.button("🚀 Lancer la recherche", type="primary", use_container_width=True)

# -------------------------------------------------------------
# 9. EXÉCUTION & STATISTIQUES
# -------------------------------------------------------------
requetes_calculees = preparer_requetes(mot_cle)

if btn_chercher or "resultats" not in st.session_state:
    label_recherche = mot_cle if mot_cle else "Toutes opportunités"
    cible_label = f"{zone_info['search_city']} ({rayon} km)"
    
    with st.spinner(f"Recherche de « {label_recherche} » sur {cible_label}..."):
        toutes_offres = []
        stats_sources = {}
        
        if "France Travail" in sources_actives:
            ft_res, ft_msg = fetch_france_travail(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(ft_res)
            stats_sources["France Travail"] = len(ft_res)
            if ft_msg != "OK": st.error(f"⚠️ Alerte France Travail : {ft_msg}")
                
        if "Adzuna" in sources_actives:
            adz_res, adz_msg = fetch_adzuna(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(adz_res)
            stats_sources["Adzuna"] = len(adz_res)
            if adz_msg != "OK": st.warning(f"⚠️ Alerte Adzuna : {adz_msg}")
            
        if "Jooble" in sources_actives:
            jb_res, jb_msg = fetch_jooble(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(jb_res)
            stats_sources["Jooble"] = len(jb_res)
            if jb_msg != "OK": st.warning(f"⚠️ Alerte Jooble : {jb_msg}")
            
        if "Indeed & LinkedIn (JSearch)" in sources_actives:
            js_res, js_msg = fetch_jsearch(requetes_calculees, zone_info, rayon)
            toutes_offres.extend(js_res)
            stats_sources["Indeed/LinkedIn"] = len(js_res)
            if js_msg != "OK": st.warning(f"⚠️ Alerte Indeed/LinkedIn : {js_msg}")
        
        uniques = {}
        for off in toutes_offres:
            cle = f"{off['titre'].lower().strip()}_{off['entreprise'].lower().strip()}"
            if cle not in uniques: uniques[cle] = off
                
        st.session_state["resultats"] = list(uniques.values())
        st.session_state["stats_sources"] = stats_sources

offres_brutes = st.session_state.get("resultats", [])
stats_aff = st.session_state.get("stats_sources", {})
offres_affichees = [job for job in offres_brutes if correspond_contrat(job, contrats_choisis)]

titre_metier = f" pour « {mot_cle} »" if mot_cle else ""
precision_geo = f"{zone_choisie.split()[0]} + {rayon} km"
st.markdown(f"### **{len(offres_affichees)} opportunités répertoriées**{titre_metier} ({precision_geo})")

if stats_aff:
    details_sources = " | ".join([f"**{src}** : {cnt}" for src, cnt in stats_aff.items()])
    st.caption(f"📊 Flux collectés : {details_sources}")

# -------------------------------------------------------------
# 10. ONGLETS D'AFFICHAGE RESPONSIVE
# -------------------------------------------------------------
tab_liste, tab_map, tab_cpf = st.tabs(["📋 Liste des offres", "🗺️ Carte interactive", "🎓 Formations & CPF"])

with tab_liste:
    if not offres_affichees:
        st.warning("Aucune offre ne correspond à ces critères. Essayez d'augmenter le rayon kilométrique ou de réinitialiser le filtre de contrat.")
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
            st.link_button("👉 Voir l'offre & Postuler", job["url"], use_container_width=True)
            st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

with tab_map:
    st.subheader(f"Zone couverte : {zone_choisie}")
    m = folium.Map(location=[zone_info["lat"], zone_info["lon"]], zoom_start=9)
    folium.Circle(location=[zone_info["lat"], zone_info["lon"]], radius=rayon * 1000, color="#2563eb", fill=True, fill_opacity=0.15, popup=f"Rayon couvert : {rayon} km").add_to(m)
    folium.Marker([zone_info["lat"], zone_info["lon"]], popup=f"{zone_choisie}", icon=folium.Icon(color="blue", icon="bullseye", prefix="fa")).add_to(m)
    st_folium(m, width="100%", height=450)

with tab_cpf:
    sujet_formation = mot_cle.upper() if mot_cle else "TOUS SECTEURS"
    lieu_dynamique = f"{zone_info['search_city']} et bassin de {rayon} km"
    
    st.subheader(f"Formations & CPF ({sujet_formation})")
    st.write(f"Opportunités d'évolution identifiées pour la zone **{lieu_dynamique}** :")
    
    st.markdown(f"""
    <div class="job-card">
        <div class="job-title">Titre Professionnel & Certification {sujet_formation}</div>
        <div class="job-company">🎓 AFPA / GRETA Occitanie</div>
        <div class="job-badges">
            <span class="badge badge-loc">📍 {lieu_dynamique} (Présentiel ou Visio)</span>
            <span class="badge badge-salary">💰 100% Eligible CPF / France Travail</span>
        </div>
        <div class="job-desc">Mettez à jour vos compétences et obtenez une certification reconnue par l'État pour maximiser vos chances de recrutement sur ce bassin d'emploi.</div>
    </div>
    
    <div class="job-card">
        <div class="job-title">Management, Réglementation & Normes Qualité</div>
        <div class="job-company">🎓 CNAM Occitanie / Apave</div>
        <div class="job-badges">
            <span class="badge badge-loc">📍 Accompagnement Région Occitanie</span>
            <span class="badge badge-salary">💰 Plan Entreprise / OPCO / CPF</span>
        </div>
        <div class="job-desc">Formations courtes et spécialisées adaptées aux professionnels souhaitant évoluer vers des postes à responsabilité.</div>
    </div>
    
    <div class="job-card">
        <div class="job-title">Validation des Acquis de l'Expérience (VAE)</div>
        <div class="job-company">🎓 Région Occitanie</div>
        <div class="job-badges">
            <span class="badge badge-loc">📍 {lieu_dynamique} (Accompagnement de proximité)</span>
            <span class="badge badge-salary">💰 Prise en charge intégrale Région</span>
        </div>
        <div class="job-desc">Transformez votre expérience acquise sur le terrain en un diplôme officiel sans retourner sur les bancs de l'école.</div>
    </div>
    """, unsafe_allow_html=True)
