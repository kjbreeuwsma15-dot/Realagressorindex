import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile
from datetime import datetime, timedelta

# --- 1. CORE LOGIC ---
def calculate_score(stability, strikes):
    aggression_penalty = min(70, strikes * 2)
    non_aggression_score = 70 - aggression_penalty
    stability_score = (stability / 100) * 30
    return round(non_aggression_score + stability_score, 1)

st.set_page_config(page_title="Real Peace Index", layout="wide")

# --- 2. DATA INGESTION (24H STACK) ---
@st.cache_data(ttl=900)
def get_24h_kinetic_data():
    all_strikes = []
    # Fetching last 12 intervals (3 hours) for this demo to ensure speed
    # Increase range(96) for full 24h
    for i in range(12): 
        time_slot = datetime.utcnow() - timedelta(minutes=15 * i)
        stamp = time_slot.strftime("%Y%m%d%H") + str((time_slot.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, usecols=[26, 52, 53, 54])
                        df.columns = ['EventCode', 'Country', 'Lat', 'Long']
                        strikes = df[df['EventCode'].astype(str).str.startswith('19')].dropna()
                        all_strikes.append(strikes)
        except: continue
    return pd.concat(all_strikes) if all_strikes else pd.DataFrame()

# --- 3. THE UI & SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Methodology")
    st.write("70% Non-Aggression / 30% Stability")
    st.info("The map aggregates strikes. Larger dots = more frequent strikes at that coordinate.")

try:
    live_data = get_24h_kinetic_data()
    live_data['Country'] = live_data['Country'].str.split(',').str[-1].str.strip()

    # AGGREGATE overlapping points for the map
    map_data = live_data.groupby(['Lat', 'Long', 'Country']).size().reset_index(name='StrikeCount')

    # LEADERBOARD DATA
    counts = live_data['Country'].value_counts().reset_index()
    counts.columns = ['Country', 'Strikes']
    stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
    counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
    counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
    counts = counts.sort_values('Score').reset_index(drop=True)
    counts.insert(0, 'Rank', range(1, len(counts) + 1))

    # SEARCH / CLICKABLE FILTER
    st.title("🛡️ Real Peace Index: Live Aggression Audit")
    target = st.selectbox("Select a country to zoom into their specific impact zones:", 
                          ["Global View"] + list(counts['Country'].unique()))

    col1, col2 = st.columns([2, 1])

    with col1:
        # Filter map based on selection
        filtered_map = map_data if target == "Global View" else map_data[map_data['Country'] == target]
        
        fig = px.scatter_geo(filtered_map, lat='Lat', lon='Long', 
                             size='StrikeCount', # DOT SIZE based on frequency
                             hover_name='Country',
                             hover_data={'StrikeCount': True, 'Lat': False, 'Long': False},
                             projection="natural earth",
                             title=f"Kinetic Impact Zones: {target}")

        # HIGH VISIBILITY BORDERS & DARK THEME
        fig.update_geos(
            showcountries=True, countrycolor="DimGray", # Clearly show borders
            showland=True, landcolor="#1a1a1a",
            showocean=True, oceancolor="#0e1117",
            showlakes=False,
            resolution=50
        )
        fig.update_traces(marker=dict(color="#ff4b4b", opacity=0.8, line=dict(width=1, color='white')))
        fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=600)
        
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("📉 Aggressor Leaderboard")
        st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Waiting for GDELT broadcast... {e}")
