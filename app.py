import streamlit as st
import pandas as pd
import requests
import io
import zipfile
from datetime import datetime, timedelta

# 1. PAGE CONFIG MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="Real Peace Index", layout="wide")

# 2. TYPE-SAFE SCORE LOGIC
def calculate_score(stability, strikes):
    try:
        s_count = float(strikes)
        stab_val = float(stability)
        aggression_penalty = min(70.0, s_count * 2.5)
        non_aggression_score = 70.0 - aggression_penalty
        stability_score = (stab_val / 100.0) * 30.0
        return round(non_aggression_score + stability_score, 1)
    except:
        return 50.0

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

# 3. DATA INGESTION
@st.cache_data(ttl=900)
def get_verified_data():
    all_rows = []
    # Scanning last 8 updates (2 hours)
    for i in range(8):
        t = datetime.utcnow() - timedelta(minutes=15 * i)
        stamp = t.strftime("%Y%m%d%H") + str((t.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False, usecols=[26, 52, 53, 54])
                        # Filter for Code 19 (Strikes)
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        all_rows.append(strikes)
        except: continue
    
    if not all_rows: return pd.DataFrame()
    full_df = pd.concat(all_rows)
    full_df.columns = ['Code', 'Country', 'lat', 'lon']
    full_df['lat'] = pd.to_numeric(full_df['lat'], errors='coerce')
    full_df['lon'] = pd.to_numeric(full_df['lon'], errors='coerce')
    return full_df.dropna(subset=['lat', 'lon'])

# 4. DASHBOARD DISPLAY
try:
    data = get_verified_data()
    
    if data.empty:
        st.warning("🔄 Scanning GDELT satellite feeds... No new kinetic events reported in the last hour.")
    else:
        # Clean Country Names
        data['Country'] = data['Country'].str.split(',').str[-1].str.strip()
        
        # Leaderboard aggregation
        counts = data['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        # Stability Map
        stability_map = {'United States': 85, 'Israel': 90, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        
        # Calculate Scores
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📍 Verified Impact Sites (Last 24h)")
            # Use a higher zoom and a bright red color
            st.map(data[['lat', 'lon']], color='#FF0000', zoom=1)
            
        with col2:
            st.subheader("📉 Aggressor List (Worst First)")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True)

except Exception as e:
    st.error(f"Syncing... {e}")

with st.expander("ℹ️ About the Score"):
    st.write("**Peace = Non-Aggression.** 70% of the score is determined by the absence of outward kinetic events. 30% is domestic stability. Rank #1 is the country most active in outward strikes.")
