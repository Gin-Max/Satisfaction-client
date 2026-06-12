import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import time
from datetime import datetime, date

# config
API_URL = "http://api:8000"
COORDS_CACHE = "/app/cache/agences_coords.json"

st.set_page_config(
    page_title="LDLC – Satisfaction Client",
    page_icon="💻",
    layout="wide",
)

# Nominatim
def clean_store_name(name: str) -> str:
    """Nettoie le nom de l'agence pour la requête Nominatim."""
    name = name.split("·")[0].strip()
    name = name.replace(" · ", " ").strip()
    return name


def geocode_store(store_name: str) -> dict | None:
    """Géocode une agence via Nominatim (OpenStreetMap)."""
    clean = clean_store_name(store_name)
    query = f"LDLC {clean}, France"
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "LDLC-Dashboard/1.0"},
            timeout=10,
        )
        results = resp.json()
        if results:
            return {
                "lat": float(results[0]["lat"]),
                "lon": float(results[0]["lon"]),
            }
    except Exception:
        pass
    return None


@st.cache_resource(show_spinner=False)
def load_coords_cache(stores: list[str]) -> dict:
    """
    Charge ou construit le cache des coordonnées GPS.
    Géocode uniquement les agences absentes du cache.
    """
    cache = {}
    if os.path.exists(COORDS_CACHE):
        with open(COORDS_CACHE, "r") as f:
            cache = json.load(f)

    missing = [s for s in stores if s not in cache]
    if missing:
        progress = st.progress(0, text="Géocodage des agences…")
        for i, store in enumerate(missing):
            coords = geocode_store(store)
            cache[store] = coords
            time.sleep(1.1)
            progress.progress((i + 1) / len(missing), text=f"Géocodage : {store}")
        progress.empty()
        # Sauvegarde du cache
        os.makedirs(os.path.dirname(COORDS_CACHE), exist_ok=True)
        with open(COORDS_CACHE, "w") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    return cache


# api
@st.cache_data(ttl=300)
def get_stats_distribution(source: str, date_from: str = None, date_to: str = None):
    params = {"source": source}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    try:
        r = requests.get(f"{API_URL}/stats/distribution-notes", params=params, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_stats_evolution(source: str, date_from: str = None, date_to: str = None):
    params = {"source": source}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    try:
        r = requests.get(f"{API_URL}/stats/evolution-mensuelle", params=params, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_note_moyenne(source: str, date_from: str = None, date_to: str = None):
    params = {"source": source}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    try:
        r = requests.get(f"{API_URL}/stats/note-moyenne", params=params, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_total_avis(source: str, date_from: str = None, date_to: str = None):
    params = {"source": source}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    try:
        r = requests.get(f"{API_URL}/stats/total-avis", params=params, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_recent_reviews(source: str, limit: int = 10, date_from: str = None, date_to: str = None):
    params = {"source": source, "limit": limit}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    try:
        r = requests.get(f"{API_URL}/avis/recents", params=params, timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_google_stores():
    """Récupère la liste des agences Google et leurs stats depuis l'API."""
    try:
        r = requests.get(f"{API_URL}/stats/google/stores", timeout=10)
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_google_store_reviews(store: str, limit: int = 10):
    try:
        r = requests.get(
            f"{API_URL}/stats/google/store-reviews",
            params={"store": store, "limit": limit},
            timeout=10,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_google_store_distribution(store: str):
    try:
        r = requests.get(
            f"{API_URL}/stats/google/store-distribution",
            params={"store": store},
            timeout=10,
        )
        return r.json() if r.ok else {}
    except Exception:
        return {}
    
@st.cache_data(ttl=300)
def get_date_min(source: str):
    try:
        r = requests.get(f"{API_URL}/stats/date-min", params={"source": source}, timeout=10)
        return r.json() if r.ok else {}
    except Exception:
        return {}

STAR_COLORS = {
    1: "#e74c3c",
    2: "#e67e22",
    3: "#f1c40f",
    4: "#2ecc71",
    5: "#27ae60",
}


def render_stars(rating: int) -> str:
    full = "★" * rating
    empty = "☆" * (5 - rating)
    return f"{full}{empty}"


def render_review_card(review: dict):
    rating = review.get("rating", 0)
    color = STAR_COLORS.get(rating, "#888")
    store = review.get("store", "")
    store_badge = f" · <span style='color:#888;font-size:0.85em'>{store}</span>" if store else ""
    st.markdown(
        f"""
        <div style='border:1px solid #e0e0e0;border-radius:8px;padding:12px 16px;margin-bottom:10px;background:#fafafa'>
            <div style='display:flex;justify-content:space-between;align-items:center'>
                <span style='font-weight:600'>{review.get("author_name","Anonyme")}{store_badge}</span>
                <span style='color:{color};font-size:1.2em'>{render_stars(rating)}</span>
            </div>
            <div style='margin-top:6px;font-size:0.9em;color:#444'>{review.get("text","")[:300] or "<em>Pas de commentaire</em>"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# nav
with st.sidebar:
    st.image("/app/ldlc_logo.png", width=120)
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["📊 Trustpilot", "🗺️ Google"],
        label_visibility="collapsed",
    )

date_min_data = get_date_min("trustpilot")
date_min_str = date_min_data.get("date_min", "2020-01-01")[:10]
date_min = date.fromisoformat(date_min_str)

# page TP
if page == "📊 Trustpilot":
    st.title("📊 Avis Trustpilot – LDLC")

    # dates
    col_d1, col_d2, col_d3 = st.columns([2, 2, 4])
    with col_d1:
        date_from = st.date_input("Du", value=date_min, key="tp_from")
    with col_d2:
        date_to = st.date_input("Au", value=date.today(), key="tp_to")

    df_str = date_from.isoformat()
    dt_str = date_to.isoformat()

    st.markdown("---")

    # kpis
    note_data = get_note_moyenne("trustpilot", df_str, dt_str)
    note_moy = note_data.get("moyenne", 0)
    total = note_data.get("total_avis", 0)

    kpi1, kpi2 = st.columns(2)
    kpi1.metric("⭐ Note moyenne", f"{note_moy:.2f} / 5" if note_moy else "–")
    kpi2.metric("💬 Total avis", f"{total:,}".replace(",", " ") if total else "–")

    st.markdown("---")

    # distrib notes
    dist_data = get_stats_distribution("trustpilot", df_str, dt_str)
    buckets = dist_data.get("distribution", [])

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Distribution des notes")
        if buckets:
            df_dist = pd.DataFrame(buckets).sort_values("note")
            df_dist["note"] = df_dist["note"].astype(str)
            df_dist["couleur"] = df_dist["note"].map(STAR_COLORS)
            fig = px.bar(
                df_dist,
                x="note",
                y="count",
                color="note",
                color_discrete_map={str(k): v for k, v in STAR_COLORS.items()},
                labels={"note": "Note", "count": "Nombre d'avis"},
                text="count",
            )
            fig.update_layout(showlegend=False, xaxis=dict(tickmode="linear", dtick=1))
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée disponible.")

    # evo mensu
    with col_right:
        st.subheader("Évolution mensuelle")
        evol_data = get_stats_evolution("trustpilot", df_str, dt_str)
        months = evol_data.get("evolution", [])
        if months:
            df_evol = pd.DataFrame(months)
            fig2 = px.line(
                df_evol,
                x="mois",
                y="count",
                markers=True,
                labels={"mois": "Mois", "count": "Nombre d'avis"},
            )
            fig2.update_traces(line_color="#3498db")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Aucune donnée disponible.")

    st.markdown("---")

    # derniers avis
    st.subheader("Derniers avis")

    data = get_recent_reviews("trustpilot", limit=10, date_from=df_str, date_to=dt_str)
    reviews = data.get("avis", []) if isinstance(data, dict) else []

    if reviews:
        for avis in reviews:
            with st.expander(
                f"⭐ {avis.get('rating', '?')} — "
                f"{avis.get('author_name', 'Anonyme')} — "
                f"{avis.get('published_date', '')[:10] if avis.get('published_date') else ''}"
            ):
                st.write(avis.get("text", "Pas de commentaire"))

                if avis.get("has_reply"):
                    st.info(f"💬 Réponse : {avis.get('reply_message', '')}")
    else:
        st.warning("Aucun avis sur cette période.")



# Google
elif page == "🗺️ Google":
    st.title("🗺️ Avis Google – Agences LDLC")
    st.markdown("---")

    stores_data = get_google_stores()

    if not stores_data:
        st.warning("Aucune donnée Google disponible pour le moment.")
        st.stop()

    store_names = [s["store"] for s in stores_data]

    # geocodage
    with st.spinner("Chargement des coordonnées des agences…"):
        coords_cache = load_coords_cache(store_names)

    # agences
    rows = []
    for s in stores_data:
        coords = coords_cache.get(s["store"])
        if coords:
            rows.append({
                "store": s["store"],
                "note_moyenne": round(s.get("note_moyenne", 0), 2),
                "nb_avis": s.get("nb_avis", 0),
                "lat": coords["lat"],
                "lon": coords["lon"],
            })

    df_map = pd.DataFrame(rows)

    if df_map.empty:
        st.warning("Impossible de géocoder les agences pour le moment.")
        st.stop()

    # carte
    st.subheader("Carte des agences")

    fig_map = px.scatter_mapbox(
        df_map,
        lat="lat",
        lon="lon",
        hover_name="store",
        hover_data={"note_moyenne": True, "nb_avis": True, "lat": False, "lon": False},
        color="note_moyenne",
        color_continuous_scale=["#e74c3c", "#f1c40f", "#27ae60"],
        range_color=[1, 5],
        size="nb_avis",
        size_max=20,
        zoom=5,
        center={"lat": 46.8, "lon": 2.3},
        mapbox_style="open-street-map",
        labels={"note_moyenne": "Note moy.", "nb_avis": "Nb avis"},
    )
    fig_map.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, height=500)
    st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("---")

    # filtre agences
    st.subheader("Détail par agence")
    selected_store = st.selectbox(
        "Sélectionner une agence",
        options=sorted(store_names),
        index=0,
    )

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader(f"Distribution des notes – {selected_store}")

        dist = get_google_store_distribution(selected_store)

        if dist and dist.get("distribution"):
            fig = px.bar(
                dist["distribution"],
                x="note",
                y="count",
                labels={"note": "Note", "count": "Nombre d'avis"},
                color="note",
                color_continuous_scale="RdYlGn",
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Données indisponibles")

    with col_r:
        st.subheader(f"10 derniers avis – {selected_store}")
        store_reviews = get_google_store_reviews(selected_store, limit=10)
        if store_reviews:
            for avis in store_reviews:
                with st.expander(
                    f"⭐ {avis.get('rating', '?')} — {avis.get('author_name', 'Anonyme')}"
                ):
                    st.write(avis.get("text", "Pas de commentaire"))
                    if avis.get("has_reply") and avis.get("reply_message"):
                        st.info(f"💬 Réponse : {avis.get('reply_message', '')}")
        else:
            st.warning("Aucun avis disponible.")