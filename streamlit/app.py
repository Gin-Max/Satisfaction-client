import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt

API_URL = "http://api:8000"

st.set_page_config(
    page_title="LDLC - Satisfaction Client",
    page_icon="⭐",
    layout="wide"
)

st.title("⭐ LDLC — Analyse de la satisfaction client")

# récup
@st.cache_data(ttl=3600)
def get_note_moyenne():
    try:
        return requests.get(f"{API_URL}/stats/note-moyenne").json()
    except:
        return None

@st.cache_data(ttl=3600)
def get_taux_reponse():
    try:
        return requests.get(f"{API_URL}/stats/taux-reponse").json()
    except:
        return None

@st.cache_data(ttl=3600)
def get_distribution_notes():
    try:
        return requests.get(f"{API_URL}/stats/distribution-notes").json()
    except:
        return None

@st.cache_data(ttl=3600)
def get_evolution_mensuelle():
    try:
        return requests.get(f"{API_URL}/stats/evolution-mensuelle").json()
    except:
        return None

@st.cache_data(ttl=3600)
def get_verified():
    try:
        return requests.get(f"{API_URL}/stats/verified").json()
    except:
        return None

@st.cache_data(ttl=3600)
def get_avis():
    try:
        return requests.get(f"{API_URL}/avis").json()
    except:
        return None


# KPI
st.subheader("Vue générale")

note_data = get_note_moyenne()
reponse_data = get_taux_reponse()

col1, col2, col3 = st.columns(3)

with col1:
    if note_data:
        st.metric("Note moyenne", f"{note_data['moyenne']} / 5")
    else:
        st.metric("Note moyenne", "N/A")

with col2:
    if note_data:
        st.metric("Total avis", note_data["total_avis"])
    else:
        st.metric("Total avis", "N/A")

with col3:
    if reponse_data:
        st.metric("Taux de réponse", f"{reponse_data['taux']} %")
    else:
        st.metric("Taux de réponse", "N/A")

st.divider()


# Distribution des notes + vérifiés
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Distribution des notes")
    dist_data = get_distribution_notes()
    if dist_data:
        fig = px.bar(
            dist_data["distribution"],
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

with col_right:
    st.subheader("Avis vérifiés vs non vérifiés")
    verified_data = get_verified()
    if verified_data:
        labels = ["Vérifié" if v["verifie"] else "Non vérifié"
                  for v in verified_data["verification"]]
        values = [v["count"] for v in verified_data["verification"]]
        fig = px.pie(
            names=labels,
            values=values,
            color_discrete_sequence=["#2ecc71", "#e74c3c"]
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Données indisponibles")

st.divider()

# Evolution mensuelle
st.subheader("Évolution mensuelle des avis")
evolution_data = get_evolution_mensuelle()
if evolution_data:
    fig = px.line(
        evolution_data["evolution"],
        x="mois",
        y="count",
        labels={"mois": "Mois", "count": "Nombre d'avis"},
        markers=True,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Données indisponibles")

st.divider()

# Taux de réponse
st.subheader("Réponses de l'entreprise")
if reponse_data:
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=reponse_data["taux"],
            title={"text": "Taux de réponse (%)"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#2ecc71"},
                "steps": [
                    {"range": [0, 33], "color": "#e74c3c"},
                    {"range": [33, 66], "color": "#f39c12"},
                    {"range": [66, 100], "color": "#2ecc71"},
                ]
            }
        ))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.metric("Avis avec réponse", reponse_data["avec_reponse"])
        st.metric("Avis sans réponse", reponse_data["sans_reponse"])
else:
    st.warning("Données indisponibles")

st.divider()


# nuage de mots
st.subheader("Nuage de mots des avis")
avis_data = get_avis()
if avis_data and avis_data["avis"]:
    textes = " ".join([a["text"] for a in avis_data["avis"] if a.get("text")])
    if textes:
        wordcloud = WordCloud(
            width=800,
            height=400,
            background_color="white",
            colormap="RdYlGn",
            max_words=100
        ).generate(textes)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
else:
    st.warning("Données indisponibles")

st.divider()

# derniers avis
st.subheader("Derniers avis")
if avis_data and avis_data["avis"]:
    avis_tries = sorted(
        avis_data["avis"],
        key=lambda x: x.get("published_date") or "",
        reverse=True
    )[:10]
    for avis in avis_tries:
        with st.expander(f"⭐ {avis.get('rating', '?')} — {avis.get('author_name', 'Anonyme')} — {avis.get('published_date', '')[:10] if avis.get('published_date') else ''}"):
            st.write(avis.get("text", "Pas de commentaire"))
            if avis.get("has_reply"):
                st.info(f"💬 Réponse : {avis.get('reply_message', '')}")