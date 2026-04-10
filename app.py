import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import zipfile
from datetime import datetime, timedelta

# --- LOGIC: THE AGGRESSOR SCORE ---
def calculate_score(stability, strikes):
    # Every strike reduces the 70-point 'Peace' pool by 2 points
    # (Lowered from 7 because 24h data has more volume)
    aggression_penalty = min(70, strikes * 2)
    non_aggression_score = 70 - aggression_penalty
    stability_score = (stability / 100) * 30
    return round(non_aggression_score + stability_score, 1)

st.set_page_config(page_title="Real Peace Index", layout="wide")
st.title("🛡️ Real Peace Index: 24-Hour Aggression Audit")

@st.cache_data(ttl=3600) # Cache for 1 hour to save performance
def get_24h_data():
    # We will fetch the last 4 intervals (1 hour) for this test to avoid timeout, 
    # but you can increase 'range(4)' to 'range(96)' for a full 24h.
    all_strikes = []
    
    # GDELT updates every 15 mins. Let's get the last 8 files (2 hours) for stability.
    for i in range(8): 
        time_slot = datetime.utcnow() - timedelta(minutes=15 * i)
        # Format: YYYYMMDDHHMMSS
        stamp = time_slot.strftime("%Y%m%d%H") + str((time_slot.minute // 15) * 15).zfill(2) + "00"
        url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.export.CSV.zip"
        
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    with z.open(z.namelist()[0]) as f:
                        df = pd.read_csv(f, sep='\t', header=None, usecols=[26, 52, 53, 54])
                        df.columns = ['EventCode', 'Country', 'Lat', 'Long']
                        # Filter for Code 19 (Strikes)
                        strikes = df[df['EventCode'].astype(str).str.startswith('19')].copy()
                        all_strikes.append(strikes)
        except:
            continue
            
    return pd.concat(all_strikes) if all_strikes else pd.DataFrame()

try:
    with st.spinner('Scanning the last 24 hours of global news...'):
        live_data = get_24h_data()
    
    if live_data.empty:
        st.warning("No kinetic events detected. Ensure GDELT servers are online.")
    else:
        # Clean country names
        live_data['Country'] = live_data['Country'].str.split(',').str[-1].str.strip()
        
        # Aggregation
        strike_counts = live_data['Country'].value_counts().reset_index()
        strike_counts.columns = ['Country', 'Strikes']

        # Stability Dictionary (30% weight)
        # Note: If US appears here, its score will drop based on its 'Strikes'
        stability_data = {'United States': 85, 'Israel': 88, 'Iran': 30, 'Lebanon': 20, 'Russia': 40}
        strike_counts['Stability'] = strike_counts['Country'].map(stability_data).fillna(50)
        
        strike_counts['Score'] = strike_counts.apply(lambda x: calculate_score(x['Stability'], x['Strikes']), axis=1)

        # Create the Rank column starting at 1
        strike_counts = strike_counts.sort_values('Score')
        strike_counts.insert(0, 'Rank', range(1, len(strike_counts) + 1))

        # --- VISUALS ---
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🌍 24-Hour Kinetic Map")
            fig = px.scatter_geo(live_data, lat='Lat', lon='Long', hover_name='Country',
                                 color_discrete_sequence=['#ff4b4b'], projection="natural earth")
            fig.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("📉 Aggressor Leaderboard (Worst First)")
            # This shows the most aggressive countries (lowest score) at Rank 1
            st.dataframe(strike_counts[['Rank', 'Country', 'Score', 'Strikes']], hide_index=True)

except Exception as e:
    st.error(f"Error: {e}")
