Python
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile

# --- LOGIC: 70% AGGRESSION / 30% STABILITY ---
def calculate_score(stability, strikes):
    aggression_penalty = min(70, strikes * 7)
    non_aggression_score = 70 - aggression_penalty
    stability_score = (stability / 100) * 30
    return round(non_aggression_score + stability_score, 1)

st.set_page_config(page_title="TruthWatch AI", layout="wide")
st.title("🛡️ TruthWatch: The Real-Time Aggressor Index")

@st.cache_data(ttl=900) 
def get_live_events():
    master_url = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
    r = requests.get(master_url)
    export_url = r.text.split('\n')[0].split(' ')[2]
    
    resp = requests.get(export_url)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        content_file = z.namelist()[0]
        with z.open(content_file) as f:
            # UPDATED COLUMN SELECTION:
            # 26=EventCode, 52=FullCountryName, 53=Lat, 54=Long
            df = pd.read_csv(f, sep='\t', header=None, usecols=[26, 52, 53, 54])
            df.columns = ['EventCode', 'Country', 'Lat', 'Long']
    
    # Filter for Military/Kinetic Events (Code 190-196)
    strikes = df[df['EventCode'].astype(str).str.startswith('19')].copy()
    return strikes

try:
    live_data = get_live_events()
    
    if live_data.empty:
        st.warning("No kinetic events detected in the last 15 minutes.")
    else:
        # 1. Clean up Country names (GDELT sometimes includes cities, we just want the last part)
        live_data['Country'] = live_data['Country'].str.split(',').str[-1].str.strip()
        
        # 2. Count strikes
        strike_counts = live_data['Country'].value_counts().reset_index()
        strike_counts.columns = ['Country', 'Strikes']

        # 3. Dynamic Stability (30% weight) - Defaulting to 50 for all countries not in this list
        stability_data = {'United States': 88, 'Israel': 90, 'Iran': 30, 'Lebanon': 20, 'Russia': 40, 'Palestine': 15}
        strike_counts['Stability'] = strike_counts['Country'].map(stability_data).fillna(50)
        
        # 4. Calculate Score
        strike_counts['Score'] = strike_counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)

        # --- VISUALS ---
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🌍 Live Kinetic Event Map")
            fig = px.scatter_geo(live_data, lat='Lat', lon='Long', hover_name='Country',
                                 color_discrete_sequence=['#ff4b4b'], projection="natural earth")
            # This makes the map dark and professional
            fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📊 Real Peace Leaderboard")
            # Sorting so the most aggressive (lowest score) is at the top
            st.dataframe(strike_counts[['Country', 'Score', 'Strikes']].sort_values('Score'), hide_index=True)

except Exception as e:
    st.error(f"Syncing with GDELT stream... {e}")
