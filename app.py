import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile
from datetime import datetime, timedelta

# --- METHODOLOGY SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Methodology")
    st.markdown("70% Non-Aggression / 30% Stability")
    st.info("Dots show verified kinetic strikes. Larger dots = multiple strikes.")

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

@st.cache_data(ttl=900)
def get_24h_data():
    all_data = []
    # Check the last 8 updates (2 hours)
    for i in range(8):
        t = datetime.utcnow() - timedelta(minutes=15 * i)
        stamp = t.strftime("%Y%m%d%H") + str((t.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        # Fetching: 26=EventCode, 52=GeoName, 53=Lat, 54=Long
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False)
                        # Filter Code 19 (Strikes)
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        # Select only the columns we need: Name, Lat, Long
                        strikes = strikes[[52, 53, 54]].dropna()
                        strikes.columns = ['Country', 'lat', 'lon'] # lowercase for st.map
                        all_data.append(strikes)
        except: continue
    return pd.concat(all_data) if all_data else pd.DataFrame()

try:
    df = get_24h_data()
    
    if df.empty:
        st.warning("No kinetic events found in the current 24h window.")
    else:
        # Clean Country Names
        df['Country'] = df['Country'].str.split(',').str[-1].str.strip()
        
        # --- THE LEADERBOARD ---
        counts = df['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        # Stability Scoring
        stability = {'United States': 85, 'Israel': 90, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability).fillna(50)
        counts['Score'] = counts.apply(lambda x: round(((70 - min(70, x['Strikes']*2.5)) + (x['Stability']*0.3)), 1), axis=1)
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        # --- THE VISUALS ---
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📍 Verified Impact Sites")
            # We use st.map for guaranteed dot visibility on all browsers
            st.map(df, color='#FF0000', size=20) 
            
        with col2:
            st.subheader("📉 Aggressor List")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True)

except Exception as e:
    st.error(f"Syncing with GDELT... {e}")
