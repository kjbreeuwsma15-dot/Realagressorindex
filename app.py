import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import gzip

# --- THE LOGIC: 70% AGGRESSION / 30% STABILITY ---
def calculate_score(stability, strikes):
    # Penalty: -7 points for every offensive event detected in this window
    aggression_penalty = min(70, strikes * 7)
    non_aggression_score = 70 - aggression_penalty
    stability_score = (stability / 100) * 30
    return round(non_aggression_score + stability_score, 1)

st.set_page_config(page_title="TruthWatch AI", layout="wide")
st.title("🛡️ TruthWatch: The Real-Time Aggressor Index")
st.markdown("Fetching live data from the **GDELT Global Stream** (No API Key Required)")

# --- DATA INGESTION (GDELT LIVE FEED) ---
@st.cache_data(ttl=900) # Refresh every 15 mins
def get_live_events():
    # GDELT Last 15 Minute File List
    master_url = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
    r = requests.get(master_url)
    # The first URL in this file is the 'export' file (physical events)
    export_url = r.text.split('\n')[0].split(' ')[2]
    
    # Download and unzip the CSV
    resp = requests.get(export_url)
    with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as f:
        # GDELT doesn't have headers in the file, we map the columns we need
        # Column 26 = EventCode, 53 = ActionGeo_Lat, 54 = ActionGeo_Long, 60 = ActionGeo_CountryCode
        df = pd.read_csv(f, sep='\t', header=None, usecols=[26, 53, 54, 60])
        df.columns = ['EventCode', 'Lat', 'Long', 'Country']
        
    # Filter for 'Military Strikes / Attacks' (Event Codes 190-196)
    strikes = df[df['EventCode'].astype(str).str.startswith('19')]
    return strikes

try:
    live_data = get_live_events()
    strike_counts = live_data['Country'].value_counts().reset_index()
    strike_counts.columns = ['Country', 'Strikes']

    # --- MERGE WITH STABILITY DATA ---
    # In a real app, you'd pull this from a static CSV of World Bank data
    stability_map = {'US': 88, 'IS': 99, 'IL': 90, 'IR': 30, 'LE': 20, 'RU': 40}
    strike_counts['Stability'] = strike_counts['Country'].map(stability_map).fillna(50)
    strike_counts['Score'] = strike_counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)

    # --- DISPLAY ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Live Aggression Heatmap (Last 15 Mins)")
        fig = px.scatter_geo(live_data, lat='Lat', lon='Long', 
                             color_discrete_sequence=['#ff4b4b'],
                             projection="natural earth", title="Recent Kinetic Events")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Aggressor Leaderboard")
        st.dataframe(strike_counts[['Country', 'Score', 'Strikes']].sort_values('Score'))

except Exception as e:
    st.error(f"Waiting for GDELT broadcast... {e}")

st.sidebar.markdown("### 🔍 Why this exists")
st.sidebar.write("Mainstream indexes value 'Domestic Stability'. We value 'Not Bombing Others'. 70% of this score is based on outward non-aggression.")