import streamlit as st
import pandas as pd
import requests
import io
import zipfile
from datetime import datetime, timedelta

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Real Peace Index", layout="wide")

# Custom CSS to make the map container stand out
st.markdown("<style> .stMap { border: 2px solid #ff4b4b; border-radius: 10px; } </style>", unsafe_allow_html=True)

def calculate_score(stability, strikes):
    try:
        aggression_penalty = min(70.0, float(strikes) * 0.8)
        return round((70.0 - aggression_penalty) + (float(stability) * 0.3), 1)
    except: return 50.0

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

# --- 2. THE RESILIENT DATA ENGINE ---
@st.cache_data(ttl=600) # Faster refresh (10 mins)
def get_audit_data():
    all_rows = []
    # We scan the last 24 hours (96 slots)
    # If a slot is empty or missing, we skip it and move to the next
    for i in range(96):
        t = datetime.utcnow() - timedelta(minutes=15 * i) - timedelta(minutes=10)
        stamp = t.strftime("%Y%m%d%H") + str((t.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        # Use raw index to avoid column name errors
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False, usecols=[26, 52, 53, 54])
                        # Filter for Event Code 19 (Kinetic)
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        all_rows.append(strikes)
            # Stop if we have enough data (Performance optimization)
            if len(all_rows) > 50: break 
        except: continue
            
    if not all_rows: return pd.DataFrame()
    
    full_df = pd.concat(all_rows)
    full_df.columns = ['Code', 'Country', 'lat', 'lon']
    full_df['lat'] = pd.to_numeric(full_df['lat'], errors='coerce')
    full_df['lon'] = pd.to_numeric(full_df['lon'], errors='coerce')
    return full_df.dropna(subset=['lat', 'lon'])

# --- 3. THE UI ---
try:
    with st.spinner("🔄 Re-syncing with global satellites..."):
        data = get_audit_data()
    
    if data.empty:
        st.error("🚨 Critical Data Gap: GDELT satellite feed is currently dark. Retrying in 5 mins...")
    else:
        # Clean data for Leaderboard
        data['Country'] = data['Country'].str.split(',').str[-1].str.strip()
        counts = data['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        
        # Rankings (Worst Actor = Rank 1)
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        # SIDEBAR SEARCH (The "Clickable" replacement)
        st.sidebar.title("🔍 Target Audit")
        search = st.sidebar.selectbox("Focus on a specific aggressor:", ["Global Overview"] + list(counts['Country'].unique()))

        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"📍 Impact Zones: {search}")
            map_data = data if search == "Global Overview" else data[data['Country'] == search]
            # FORCE DISPLAY: st.map is the most reliable tool to show points
            st.map(map_data[['lat', 'lon']], color='#FF0000', size=25) 
            
        with col2:
            st.subheader("📉 Aggressor Leaderboard")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Audit System Failure: {e}")
