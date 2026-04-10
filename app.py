import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile

# --- THE LOGIC: 70% AGGRESSION / 30% STABILITY ---
def calculate_score(stability, strikes):
    # Penalty: Every offensive event reduces score by 7 points
    aggression_penalty = min(70, strikes * 7)
    non_aggression_score = 70 - aggression_penalty
    stability_score = (stability / 100) * 30
    return round(non_aggression_score + stability_score, 1)

st.set_page_config(page_title="TruthWatch AI", layout="wide")
st.title("🛡️ TruthWatch: The Real-Time Aggressor Index")
st.markdown("Auditing global 'Peace' through live kinetic data from **GDELT**.")

# --- DATA INGESTION (FIXED ZIP LOGIC) ---
@st.cache_data(ttl=900) 
def get_live_events():
    master_url = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
    r = requests.get(master_url)
    # Get the URL for the 'export' file (physical events)
    export_url = r.text.split('\n')[0].split(' ')[2]
    
    resp = requests.get(export_url)
    # USE ZIPFILE INSTEAD OF GZIP
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # Get the first filename inside the zip
        content_file = z.namelist()[0]
        with z.open(content_file) as f:
            # GDELT columns: 26=EventCode, 53=Lat, 54=Long, 60=CountryCode
            df = pd.read_csv(f, sep='\t', header=None, usecols=[26, 53, 54, 60])
            df.columns = ['EventCode', 'Lat', 'Long', 'Country']
    
    # Event Code 19 = Assault/Kinetic strikes
    strikes = df[df['EventCode'].astype(str).str.startswith('19')].copy()
    return strikes

try:
    live_data = get_live_events()
    
    if live_data.empty:
        st.warning("No kinetic events detected in the last 15 minutes. The world is currently quiet.")
    else:
        # Count strikes per country
        strike_counts = live_data['Country'].value_counts().reset_index()
        strike_counts.columns = ['Country', 'Strikes']

        # Stability map (0-100)
        stability_map = {'US': 88, 'IS': 99, 'IL': 90, 'IR': 30, 'LE': 20, 'RU': 40}
        strike_counts['Stability'] = strike_counts['Country'].map(stability_map).fillna(50)
        strike_counts['Score'] = strike_counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)

        # --- LAYOUT ---
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📍 Live Kinetic Event Map")
            fig = px.scatter_geo(live_data, lat='Lat', lon='Long', 
                                 color_discrete_sequence=['#ff4b4b'],
                                 projection="natural earth")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📊 Real Peace Leaderboard")
            st.dataframe(strike_counts[['Country', 'Score', 'Strikes']].sort_values('Score'))

except Exception as e:
    st.error(f"Syncing with GDELT stream... Error details: {e}")

st.divider()
st.info("💡 **How to read this:** Lower scores = More aggressive. A country with 100% domestic stability but 10 outward strikes will rank worse than a country with 50% stability and 0 strikes.")
