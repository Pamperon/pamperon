import streamlit as st
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, commonteamroster
import pandas as pd
import datetime
import time
import requests
import urllib3
import matplotlib.pyplot as plt
import unicodedata

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="NBA Stats", layout="centered")

# 🔧 Nasconde i label vuoti sotto i widget
st.markdown("""
<style>
label[data-testid="stWidgetLabel"] > div:empty {
    display: none;
}
</style>
""", unsafe_allow_html=True)

st.title("🏀 NBA Stats")
st.markdown("Inserisci il nome di un giocatore NBA e la linea per calcolare le percentuali over/under su punti, assist, rimbalzi e P+A+R.")

@st.cache_data
def get_team_of_player(player_id):
    for team in teams.get_teams():
        try:
            roster = commonteamroster.CommonTeamRoster(team_id=team['id'], season='2024-25')
            df_roster = roster.get_data_frames()[0]
            if player_id in df_roster['PLAYER_ID'].values:
                return team['id'], team['abbreviation'], team['full_name']
            time.sleep(0.4)
        except:
            continue
    return None, None, None

@st.cache_data
def get_season_gamelog(player_id):
    gamelog = playergamelog.PlayerGameLog(player_id=player_id, season='2024-25', season_type_all_star='Regular Season')
    df = gamelog.get_data_frames()[0]
    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], errors='coerce')
    return df.sort_values(by="GAME_DATE", ascending=False)

@st.cache_data
def get_all_gamelogs(player_id):
    all_games = []
    for year in range(2000, 2025):
        season = f"{year}-{str(year + 1)[-2:]}"
        try:
            log = playergamelog.PlayerGameLog(player_id=player_id, season=season, season_type_all_star='Regular Season')
            df = log.get_data_frames()[0]
            df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], errors='coerce')
            all_games.append(df)
            time.sleep(0.4)
        except:
            continue
    if all_games:
        return pd.concat(all_games).sort_values(by="GAME_DATE", ascending=False)
    else:
        return pd.DataFrame()

def calculate_over_stats(df, col, line):
    total_games = len(df)
    over_games = (df[col] > line).sum()
    percent = round((over_games / total_games) * 100, 1) if total_games > 0 else 0
    return percent, over_games, total_games

def normalize_name(name):
    return unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8').lower()

def plot_candle_chart(df, col, line, title, rotate_xticks=45, show_labels=True, show_xticks=True):
    if df.empty:
        st.warning("⚠️ Nessun dato disponibile per il grafico.")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    df = df.sort_values(by='GAME_DATE')
    labels = df['GAME_DATE'].dt.strftime('%m/%d')
    colors = ['#00C853' if val > line else '#D50000' for val in df[col]]

    bars = ax.bar(labels, df[col], color=colors, width=0.6)
    if show_labels:
        for bar, val in zip(bars, df[col]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{val:.0f}", ha='center', va='bottom', fontsize=9, color='white', weight='bold')

    ax.axhline(line, color='gray', linestyle='--', linewidth=1.5, label=f'Linea {line}')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylabel(col)
    ax.set_xlabel('Data')
    ax.set_facecolor('#111111')
    fig.patch.set_facecolor('#111111')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    if show_xticks:
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=rotate_xticks, ha='right')
    else:
        ax.set_xticks([])
        ax.set_xticklabels([])
    ax.legend(facecolor='#111111', edgecolor='white', labelcolor='white')
    st.pyplot(fig)

# === INTERFACCIA ===

player_name_input = st.text_input("🔍 Inserisci il nome del giocatore (es: LeBron James)")

if player_name_input:
    normalized_input = normalize_name(player_name_input)
    matched_players = [p for p in players.get_active_players() if normalized_input in normalize_name(p['full_name'])]

    if len(matched_players) == 0:
        st.error("❌ Nessun giocatore trovato con questo nome.")
    else:
        selected_player = st.selectbox("✅ Scegli il giocatore corretto", matched_players, format_func=lambda p: p['full_name'])

        player_id = selected_player['id']

        st.markdown("### 📌 Scegli la metrica da visualizzare")
        metric = st.radio("", ["Punti", "Assist", "Rimbalzi", "P+A+R"], horizontal=True)

        game_type = st.radio("🎯 Scegli il tipo di partita", ["Totale", "Casa", "Ospite"], horizontal=True)

        col_map = {
            "Punti": "PTS",
            "Assist": "AST",
            "Rimbalzi": "REB",
            "P+A+R": "PAR"
        }

        df = get_season_gamelog(player_id)
        if metric == "P+A+R":
            df["PAR"] = df["PTS"] + df["AST"] + df["REB"]

        if game_type == "Casa":
            df = df[df['MATCHUP'].str.contains("vs")]
        elif game_type == "Ospite":
            df = df[df['MATCHUP'].str.contains("@")]

        col = col_map[metric]
        default_lines = {"PTS": 20.5, "AST": 5.5, "REB": 6.5, "PAR": 30.5}
        line = st.number_input(f"🎯 Inserisci la linea {metric.lower()}", min_value=0.0, max_value=100.0, value=default_lines[col], step=0.5)

        st.subheader("📈 Visualizza il grafico")
        chart_range = st.selectbox("Seleziona l'intervallo del grafico", ["Ultime 5", "Ultime 10", "Intera stagione"])

        if chart_range == "Ultime 5":
            plot_candle_chart(df.head(5), col, line, f"Grafico Ultime 5 Partite - {metric}")
        elif chart_range == "Ultime 10":
            plot_candle_chart(df.head(10), col, line, f"Grafico Ultime 10 Partite - {metric}")
        elif chart_range == "Intera stagione":
            plot_candle_chart(df, col, line, f"Grafico Intera Stagione - {metric}", rotate_xticks=0, show_labels=False, show_xticks=False)

        st.subheader(f"📊 Statistiche {metric.lower()}")
        st.markdown(f"**{selected_player['full_name']}**\n\nLinea: **{line}**")

        pct_5, over_5, _ = calculate_over_stats(df.head(5), col, line)
        st.write(f"**Ultime 5 partite**: {pct_5}% over ({over_5}/5)")

        pct_10, over_10, _ = calculate_over_stats(df.head(10), col, line)
        st.write(f"**Ultime 10 partite**: {pct_10}% over ({over_10}/10)")

        pct_all, over_all, total_all = calculate_over_stats(df, col, line)
        st.write(f"**Intera stagione**: {pct_all}% over ({over_all}/{total_all})")

        team_abbrs = ["Scegli un avversario..."] + sorted(set([team['abbreviation'] for team in teams.get_teams()]))
        selected_opponent = st.selectbox("🆚 Seleziona la squadra avversaria", team_abbrs)

        if selected_opponent != "Scegli un avversario...":
            df_all = get_all_gamelogs(player_id)
            if metric == "P+A+R":
                df_all["PAR"] = df_all["PTS"] + df_all["AST"] + df_all["REB"]
            if game_type == "Casa":
                df_all = df_all[df_all['MATCHUP'].str.contains("vs")]
            elif game_type == "Ospite":
                df_all = df_all[df_all['MATCHUP'].str.contains("@")]
            df_vs_next = df_all[df_all['MATCHUP'].str.contains(selected_opponent)]
            pct_vs, over_vs, total_vs = calculate_over_stats(df_vs_next, col, line)
            st.write(f"**Vs {selected_opponent} (carriera)**: {pct_vs}% over ({over_vs}/{total_vs})")
