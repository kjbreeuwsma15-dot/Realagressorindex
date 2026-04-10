import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile
from datetime import datetime, timedelta

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="Real Peace Index", layout="wide", initial_sidebar_state="expanded")

def calculate_score(stability, strikes):
    try:
        # Penalty multiplier adjusted for hourly sampling
        aggression_penalty = min(70.0, float(strikes) * 1.5)
        return round((70.0 - aggression_penalty) + (float(stability) * 0.3), 1)
    except: return 50.0

st.title("🛡️ Real Peace Index: 24h Aggression Audit")

# --- 2. PRO-GRADE DATA INGESTION ---
@st.cache_data(ttl=900)
def fetch_24h_spread():
    all_rows = []
    # OPTIMIZATION: Pull 1 file per hour for 24 hours. 
    # This prevents server timeouts and bans while maintaining a 24h visual window.
    for i in range(24):
        # Target the top of the hour (00) to ensure file consistency
        t = datetime.utcnow() - timedelta(hours=i)
        stamp = t.strftime("%Y%m%d%H") + "0000"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, low_memory=False, usecols=[26, 52, 53, 54])
                        # Filter for Event Code 19 (Kinetic Strikes)
                        strikes = df[df[26].astype(str).str.startswith('19')].copy()
                        all_rows.append(strikes)
        except: 
            continue # Silently skip missing hourly files

    # Fallback if the entire connection is blocked
    if not all_rows: 
        return pd.DataFrame(columns=['Code', 'Country', 'lat', 'lon'])
    
    df = pd.concat(all_rows)
    df.columns = ['Code', 'Country', 'lat', 'lon']
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    return df.dropna(subset=['lat', 'lon'])

# --- 3. FETCH & PROCESS ---
with st.spinner("📡 Establishing secure connection to Global Feeds..."):
    data = fetch_24h_spread()

# --- 4. LAYOUT & INTERACTIVITY ---
col1, col2 = st.columns([2, 1])

# The "Clickable" Sidebar Filter
with st.sidebar:
    st.header("🔍 Target Audit")
    st.markdown("70% Non-Aggression / 30% Stability")
    
    if not data.empty:
        # Generate a clean list of countries currently in the feed
        countries = ["Global Overview"] + sorted(list(data['Country'].str.split(',').str[-1].str.strip().dropna().unique()))
        target = st.selectbox("Focus Map on Aggressor:", countries)
    else:
        target = "Global Overview"
        st.warning("Feed unavailable.")

with col1:
    st.subheader(f"📍 Kinetic Impact Zones: {target}")
    
    # Map Logic: Guarantee the map renders no matter what
    if data.empty:
        fig = px.scatter_geo(title="Awaiting Satellite Data...")
    else:
        map_df = data.copy()
        map_df['Country'] = map_df['Country'].str.split(',').str[-1].str.strip()
        
        # Filter map by sidebar selection
        if target != "Global Overview":
            map_df = map_df[map_df['Country'] == target]
            
        if map_df.empty:
            fig = px.scatter_geo(title=f"No recent strikes found for {target}")
        else:
            # Aggregate dots by intensity (multiple strikes = bigger dot)
            intensity = map_df.groupby(['lat', 'lon', 'Country']).size().reset_index(name='Intensity')
            fig = px.scatter_geo(intensity, lat='lat', lon='lon', size='Intensity', 
                                 hover_name='Country', color_discrete_sequence=['#ff4b4b'])

    # THE MAP STYLING (Dark Mode + Country Borders)
    fig.update_geos(
        showcountries=True, countrycolor="#555555",
        showland=True, landcolor="#111111",
        showocean=True, oceancolor="#000000",
        resolution=50
    )
    fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0), height=600)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📉 Aggressor List")
    
    if data.empty:
        st.info("Leaderboard offline. The world is quiet or feeds are blocked.")
    else:
        # Leaderboard Logic
        board_df = data.copy()
        board_df['Country'] = board_df['Country'].str.split(',').str[-1].str.strip()
        counts = board_df['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        
        # Stability Baseline
        stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        counts = counts.sort_values('Score').reset_index(drop=True)
        counts.insert(0, 'Rank', range(1, len(counts) + 1))
        
        st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True, use_container_width=True)
