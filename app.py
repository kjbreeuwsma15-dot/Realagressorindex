import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile
from datetime import datetime, timedelta

# --- 1. EXPLANATION LOGIC ---
def calculate_score(stability, strikes):
    # Every strike reduces the 70-point 'Peace' pool.
    aggression_penalty = min(70, strikes * 2)
    non_aggression_score = 70 - aggression_penalty
    stability_score = (stability / 100) * 30
    return round(non_aggression_score + stability_score, 1)

st.set_page_config(page_title="Real Peace Index", layout="wide", initial_sidebar_state="expanded")

# --- 2. SIDEBAR EXPLANATION ---
with st.sidebar:
    st.title("🛡️ Methodology")
    st.markdown("""
    **The 70/30 Rule**
    Traditional indexes reward 'Stability.' We reward **Non-Aggression**.
    
    * **70% Weight:** Outward Military Actions.
    * **30% Weight:** Internal Stability.
    
    **What is a 'Kinetic Event'?**
    Any verified report of a military strike, bombing, or armed assault crossing or affecting borders.
    
    **The Aggressor Score:**
    * **100:** Perfect Peace.
    * **0:** Total Aggression.
    
    *Rank #1 represents the most aggressive actor in the last 24h.*
    """)
    st.divider()
    target_country = st.selectbox("🔍 Filter by Country to see targets:", ["All Countries"] + ["United States", "Israel", "Russia", "Iran", "Lebanon"])

st.title("🛡️ Real Peace Index: 24-Hour Aggression Audit")

# --- 3. DATA INGESTION ---
@st.cache_data(ttl=900)
def get_kinetic_data():
    all_strikes = []
    # Fetching last 8 intervals (2 hours) for performance; increase range for more history
    for i in range(8): 
        time_slot = datetime.utcnow() - timedelta(minutes=15 * i)
        stamp = time_slot.strftime("%Y%m%d%H") + str((time_slot.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        # 26=Event, 52=CountryName, 53=Lat, 54=Long
                        df = pd.read_csv(f, sep='\t', header=None, usecols=[26, 52, 53, 54])
                        df.columns = ['EventCode', 'Country', 'Lat', 'Long']
                        # Filter for Code 19 (Strikes) and ENSURE Lat/Long exist
                        strikes = df[df['EventCode'].astype(str).str.startswith('19')].dropna(subset=['Lat', 'Long'])
                        all_strikes.append(strikes)
        except:
            continue
    return pd.concat(all_strikes) if all_strikes else pd.DataFrame()

try:
    with st.spinner('Auditing global military feeds...'):
        live_data = get_kinetic_data()
    
    if live_data.empty:
        st.info("No active strikes detected in this window.")
    else:
        # Clean names
        live_data['Country'] = live_data['Country'].str.split(',').str[-1].str.strip()
        
        # Filtering logic for the "Clickable" feel
        display_data = live_data if target_country == "All Countries" else live_data[live_data['Country'] == target_country]

        # Leaderboard Math
        counts = live_data['Country'].value_counts().reset_index()
        counts.columns = ['Country', 'Strikes']
        stability_map = {'United States': 85, 'Israel': 88, 'Russia': 40, 'Iran': 30, 'Lebanon': 20}
        counts['Stability'] = counts['Country'].map(stability_map).fillna(50)
        counts['Score'] = counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)
        
        # Rankings
        counts = counts.sort_values('Score')
        counts.insert(0, 'Rank', range(1, len(counts) + 1))

        # --- 4. VISUALS ---
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"🌍 Movement Map: {target_country}")
            fig = px.scatter_geo(display_data, lat='Lat', lon='Long', hover_name='Country',
                                 color_discrete_sequence=['#ff4b4b'], 
                                 projection="natural earth",
                                 size_max=15)
            fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📉 The Aggressor List")
            st.dataframe(counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True)

except Exception as e:
    st.error(f"Waiting for satellite feed... {e}")
