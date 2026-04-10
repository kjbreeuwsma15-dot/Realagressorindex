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
        aggression_penalty = min(70.0, s_count * 0.7)
        non_aggression_score = 70.0 - aggression_penalty
        stability_score = (stab_val / 100.0) * 30.0
        return round(non_aggression_score + stability_score, 1)
    except:
        return 50.0

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

# 3. ROBUST 24h DATA INGESTION
@st.cache_data(ttl=900)
def get_24h_data():
    all_rows = []
    # Progress indicator in the sidebar
    status = st.sidebar.empty()
    
    # We check 96 intervals (24 hours)
    for i in range(96):
        # We offset the time slightly to account for GDELT's processing delay
        t = datetime.utcnow() - timedelta(minutes=15 * i) - timedelta(minutes=5)
        stamp = t.strftime("%Y%m%d%H") + str((t.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False, usecols=[26, 52, 53, 54])
                        # 19 = Strikes
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        all_rows.append(strikes)
            if i % 10 == 0: status.text(f"Auditing: {int((i/96)*100)}% complete...")
        except: continue

    if not all_rows: return pd.DataFrame()
    full_df = pd.concat(all_rows)
    full_df.columns = ['Code', 'Country', 'lat', 'lon']
    full_df['lat'] = pd.to_numeric(full_df['lat'], errors='coerce')
    full_df['lon'] = pd.to_numeric(full_df['lon'], errors='coerce')
    status.text("✅ Audit Complete")
    return full_df.dropna(subset=['lat', 'lon'])

# 4. DASHBOARD
try:
    data = get_24h_data()
    
    if data.empty:
        st.error("⚠️ Data Stream Interrupted. GDELT servers are not responding to the 24h request.")
    else:
        # Clean Country Names
        data['Country'] = data['Country'].str.split(',').str[-1].str.strip()
        
        # Leaderboard
        counts = data['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        # Stability Map
        stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        # Main View
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📍 Real-Time Impact Map")
            st.map(data[['lat', 'lon']], color='#FF0000', zoom=1)
            st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} (Local Time)")
            
        with col2:
            st.subheader("📉 Aggressor List")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Global Audit Offline: {e}")
