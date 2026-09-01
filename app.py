# -------------------------------------------------------------
# 5. CONNECTEUR FRANCE TRAVAIL AVEC USER-AGENT & TIMEOUT ÉLARGI
# -------------------------------------------------------------
@st.cache_data(ttl=900)
def get_ft_token(client_id, client_secret):
    if not client_id or not client_secret:
        return None, "Identifiants FT non renseignés dans les Secrets"
    
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_key?realm=%2Fpartenaire"
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
        r = requests.post(url, headers=headers, data=data, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token"), "OK"
        return None, f"Erreur {r.status_code} : {r.text[:80]}"
    except requests.exceptions.Timeout:
        return None, "Serveur France Travail inaccessible (délai dépassé)"
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
        params = {"range": "0-49"}
        if q:
            params["motsCles"] = q
            
        if zone_info["is_region"]:
            params["region"] = zone_info["region_ft"]
        elif zone_info.get("code_insee"):
            params["commune"] = zone_info["code_insee"]
            params["distance"] = min(max(distance_km, 10), 100)
        elif zone_info.get("dept"):
            params["departement"] = zone_info["dept"]
            
        try:
            resp = requests.get(base_url, headers=headers, params=params, timeout=15)
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
            continue
    return offres, "OK"
