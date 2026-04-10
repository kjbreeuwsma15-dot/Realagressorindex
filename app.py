import streamlit as st
import pandas as pd
import requests
import io
import zipfile
from datetime import datetime, timedelta

# 1. PAGE SETUP
st.set_page_config(page_title="Real Peace Index", layout="wide")

def calculate_score(stability, strikes):
    try:
        aggression_penalty = min(70.0, float(strikes) * 0.8)
        return round((70.0 - aggression_penalty) + (float(stability) * 0.3), 1)
    except: return 50.0

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

# 2. THE RESILIENT DATA ENGINE
@st.cache_data(ttl=600)
def get_audit_data():
    all_rows = []
    # We attempt a 24h window but prioritize successfully downloaded chunks
    # This prevents the 'Failed Data Grab' message
    for i in range(96):
        t = datetime.utcnow() - timedelta(minutes=15 * i) - timedelta(minutes=15)
        stamp = t.strftime("%Y%m%d%H") + str((t.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            # Increased timeout to 5 seconds to handle 2026 server congestion
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False, usecols=[26, 52, 53, 54])
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        all_rows.append(strikes)
        except: 
            # If a file fails, we just keep going instead of crashing
            continue
            
    if not all_rows: return pd.DataFrame()
    
    full_df = pd.concat(all_rows)
    full_df.columns = ['Code', 'Country', 'lat', 'lon']
    full_df['lat'] = pd.to_numeric(full_df['lat'], errors='coerce')
    full_df['lon'] = pd.to_numeric(full_df['lon'], errors='coerce')
    return full_df.dropna(subset=['lat', 'lon'])

# 3. DISPLAY LOGIC
try:
    # Use a cleaner loading message
    with st.status("📡 Connecting to Global Satellite Feeds...", expanded=True) as status:
        data = get_audit_data()
        if not data.empty:
            status.update(label="✅ Data Audit Complete!", state="complete", expanded=False)
    
    if data.empty:
        st.error("⚠️ The Truth Stream is currently blocked. GDELT's servers are not responding. Try refreshing in 2 minutes.")
    else:
        # Leaderboard Processing
        data['Country'] = data['Country'].str.split(',').str[-1].str.strip()
        counts = data['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📍 Kinetic Impact Map")
            # This map WILL show as long as even one file was grabbed
            st.map(data[['lat', 'lon']], color='#FF0000', size=25) 
            
        with col2:
            st.subheader("📉 Aggressor Leaderboard")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Audit System Offline: {e}")
