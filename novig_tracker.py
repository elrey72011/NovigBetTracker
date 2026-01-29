import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import json
import os
from pathlib import Path

# Page config
st.set_page_config(page_title="Novig Bet Tracker", layout="wide")
st.title("🏆 Novig Real-Time Bet Tracker")

# Data file path
DATA_FILE = "novig_bets.csv"

# Initialize session state
if "bets" not in st.session_state:
    if os.path.exists(DATA_FILE):
        st.session_state.bets = pd.read_csv(DATA_FILE).to_dict('records')
    else:
        st.session_state.bets = []

# Function to get live scores from ESPN API
def get_live_score(team1, team2, sport):
    """Fetch live score from ESPN API"""
    try:
        sport_map = {
            "NCAAB": "college-basketball",
            "NCAAF": "college-football",
            "NFL": "nfl",
            "NBA": "nba",
            "MLB": "mlb"
        }
        
        sport_url = sport_map.get(sport, "college-basketball")
        
        # ESPN API for scores
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_url}/scoreboard"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            # Search for matching teams
            for event in events:
                competitors = event.get('competitions', [{}])[0].get('competitors', [])
                team_names = [c.get('team', {}).get('displayName', '').lower() for c in competitors]
                
                if any(t in ' '.join(team_names).lower() for t in [team1.lower(), team2.lower()]):
                    comp = event['competitions'][0]
                    score1 = int(competitors[0].get('score', 0) or 0)
                    score2 = int(competitors[1].get('score', 0) or 0)
                    status = event.get('status', {}).get('type', {}).get('description', 'Not Started')
                    
                    return {
                        'team1': competitors[0]['team']['displayName'],
                        'team2': competitors[1]['team']['displayName'],
                        'score1': score1,
                        'score2': score2,
                        'status': status
                    }
        return None
    except Exception as e:
        st.warning(f"Could not fetch live score: {str(e)}")
        return None

# Function to calculate bet status
def calculate_bet_status(bet, live_score):
    """Determine if bet is winning, losing, or pending"""
    if not live_score:
        return "Pending", "⏳", 0
    
    pick = bet['Pick'].strip()
    score1 = live_score['score1']
    score2 = live_score['score2']
    status = live_score['status']
    
    # Parse pick (e.g., "Duke -5.5" or "UNC +3")
    team_pick = pick.split()[0]
    spread_str = pick.split()[1] if len(pick.split()) > 1 else "0"
    
    try:
        spread = float(spread_str)
    except:
        spread = 0
    
    # Determine which team is team1 or team2
    is_team1 = team_pick.lower() in live_score['team1'].lower()
    
    if is_team1:
        adjusted_score = score1 - score2 - spread
    else:
        adjusted_score = score2 - score1 - spread
    
    win_prob = min(100, max(0, 50 + (adjusted_score * 2)))
    
    if "Final" in status or "End" in status:
        if adjusted_score > 0:
            return "✅ Won", "✅", 100
        elif adjusted_score < 0:
            return "❌ Lost", "❌", 0
        else:
            return "🟡 Push", "🟡", 50
    elif "Live" in status or "In Progress" in status:
        return f"🔄 In Progress ({win_prob}%)", "🔄", win_prob
    else:
        return "⏳ Pending", "⏳", 0

# Sidebar for adding bets
st.sidebar.header("➕ Add New Bet")

with st.sidebar.form("add_bet_form"):
    sport = st.selectbox("Sport", ["NCAAB", "NCAAF", "NFL", "NBA", "MLB"])
    teams = st.text_input("Teams (e.g., 'Duke vs UNC')")
    pick = st.text_input("Pick (e.g., 'Duke -5.5' or 'UNC +3')")
    odds = st.number_input("Odds (e.g., -110)", value=-110)
    stake = st.number_input("Stake ($)", value=10.0, min_value=0.01)
    
    if st.form_submit_button("Add Bet"):
        if teams and pick:
            new_bet = {
                "Sport": sport,
                "Teams": teams,
                "Pick": pick,
                "Odds": odds,
                "Stake": f"${stake:.2f}",
                "Added": datetime.now().strftime("%m/%d %I:%M %p"),
                "Status": "Pending"
            }
            st.session_state.bets.append(new_bet)
            
            # Save to CSV
            df = pd.DataFrame(st.session_state.bets)
            df.to_csv(DATA_FILE, index=False)
            st.success(f"✅ Bet added! Total bets: {len(st.session_state.bets)}")
        else:
            st.error("Please fill in all fields")

# Display bets with live tracking
if st.session_state.bets:
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh Live Scores"):
            st.rerun()
    
    st.subheader(f"Active Bets ({len(st.session_state.bets)})")
    
    for idx, bet in enumerate(st.session_state.bets):
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{bet['Sport']}** • {bet['Teams']}")
                st.write(f"Pick: `{bet['Pick']}` • Odds: `{bet['Odds']}` • Stake: {bet['Stake']}")
            
            with col2:
                # Fetch live score
                teams_list = bet['Teams'].split(' vs ')
                live_score = get_live_score(teams_list[0], teams_list[1], bet['Sport']) if len(teams_list) == 2 else None
                
                if live_score:
                    st.write(f"**Live Score**: {live_score['team1']} {live_score['score1']} - {live_score['team2']} {live_score['score2']}")
                    st.write(f"Status: {live_score['status']}")
                    
                    bet_status, emoji, win_prob = calculate_bet_status(bet, live_score)
                    st.session_state.bets[idx]["Status"] = bet_status
                else:
                    st.write("⏳ Fetching live score...")
                    st.write(f"Added: {bet['Added']}")
            
            with col3:
                bet_status, emoji, win_prob = calculate_bet_status(bet, live_score) if live_score else ("Pending", "⏳", 0)
                st.metric(emoji, bet_status, f"{win_prob}%")
                
                if st.button("🗑️ Remove", key=f"remove_{idx}"):
                    st.session_state.bets.pop(idx)
                    df = pd.DataFrame(st.session_state.bets)
                    df.to_csv(DATA_FILE, index=False)
                    st.rerun()
    
    # Save updated bets
    df = pd.DataFrame(st.session_state.bets)
    df.to_csv(DATA_FILE, index=False)
    
    # Summary stats
    st.divider()
    st.subheader("📊 Bet Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Bets", len(st.session_state.bets))
    with col2:
        total_stake = sum(float(bet['Stake'].replace('$', '')) for bet in st.session_state.bets)
        st.metric("Total Stake", f"${total_stake:.2f}")
    with col3:
        winning = sum(1 for bet in st.session_state.bets if "Won" in bet["Status"])
        st.metric("Winning", winning)

else:
    st.info("👈 Add your first bet to get started!")

# Footer with auto-refresh
st.divider()
col1, col2 = st.columns([1, 4])
with col1:
    refresh_interval = st.selectbox("Auto-refresh", ["Off", "10s", "30s", "60s"])
with col2:
    st.caption("Data saved to `novig_bets.csv` in your working directory")

if refresh_interval != "Off":
    import time
    interval_map = {"10s": 10, "30s": 30, "60s": 60}
    time.sleep(interval_map[refresh_interval])
    st.rerun()
