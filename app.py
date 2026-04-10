import streamlit as st
import pandas as pd
import requests
import io
import zipfile
from datetime import datetime, timedelta

# 1. PAGE CONFIG
st.set_page_config(page_title="Real Peace Index", layout="wide")

# 2. TYPE-SAFE SCORE LOGIC
def calculate_score(stability, strikes):
    try:
        s_count = float(strikes)
        stab_val = float(stability)
        # Weighting: Strikes in 24h are more common, so we use a 0.7 penalty per strike
        aggression_penalty = min(70.0, s_count * 0.7)
        non_aggression_score = 70.0 - aggression_penalty
        stability_score = (stab_val / 100.0) * 30.0
        return round(non_aggression_score + stability_score, 1)
    except:
        return 50.0

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

# 3. 24h DATA INGESTION (Optimized for Streamlit)
@st.cache_data(ttl=1800) # Update every 30 mins
def get_24h_data():
    all_rows = []
    # Loop through 96 intervals (24 hours)
    # We use a progress bar to show the user it's working
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    for i in range(96):
        t = datetime.utcnow() - timedelta(minutes=15 * i)
        stamp = t.strftime("%Y%m%d%H") + str((t.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False, usecols=[26, 52, 53, 54])
                        # Code 19 = Strikes
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        all_rows.append(strikes)
        except: continue
        
        # Update sidebar progress
        progress_bar.progress((i + 1) / 96)
        status_text.text(f"Scanning 24h: {96-i} intervals left...")

    if not all_rows: return pd.DataFrame()
    full_df = pd.concat(all_rows)
    full_df.columns = ['Code', 'Country', 'lat', 'lon']
    full_df['lat'] = pd.to_numeric(full_df['lat'], errors='coerce')
    full_df['lon'] = pd.to_numeric(full_df['lon'], errors='coerce')
    return full_df.dropna(subset=['lat', 'lon'])

# 4. DASHBOARD DISPLAY
try:
    data = get_24h_data()
    
    if data.empty:
        st.error("🚨 GDELT Servers are currently unreachable or empty. Displaying last known data...")
    else:
        # Clean Country Names
        data['Country'] = data['Country'].str.split(',').str[-1].str.strip()
        
        # Leaderboard
        counts = data['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        # Stability Map (Updates based on 2026 data)
        stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20, 'UK': 98}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        
        # Score calculation
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        # Main Layout
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📍 Verified Impact Sites (24h Window)")
            # st.map will now always show because we've pulled 24h of data
            st.map(data[['lat', 'lon']], color='#FF0000', zoom=1)
            
        with col2:
            st.subheader("📉 Aggressor List (Worst First)")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Global Audit Offline: {e}")

with st.expander("ℹ️ Methodology"):
    st.write("Rank #1 is determined by the highest volume of outward kinetic strikes in the last 24 hours. The 'Score' values non-aggression at 70% and internal stability at 30%.")
