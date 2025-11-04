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
import io
from bs4 import BeautifulSoup

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

# 📋 Sezione nuova: Incolla codice HTML per estrarre giocatori e linee
st.subheader("📋 Incolla HTML per estrarre giocatori e linee")

html_input = st.text_area("Incolla qui il codice HTML...")

if st.button("Estrai giocatori e linee") and html_input:
    soup = BeautifulSoup(html_input, "html.parser")
    all_participants = soup.find_all("div", class_="gl-MarketGroup_Wrapper")

    player_lines = []

    for group in all_participants:
        names = [tag.text.strip() for tag in group.find_all("div", class_="srb-ParticipantLabelWithTeam_Name")]
        handicaps = [tag.text.strip() for tag in group.find_all("span", class_="gl-ParticipantCenteredStacked_Handicap")]

        if len(names) > len(handicaps):
            st.warning("⚠️ Attenzione: alcuni giocatori non hanno linee associate.")

        for name, line in zip(names, handicaps):
            player_lines.append({
                "Giocatore": name,
                "Linea": line.replace(",", ".")
            })

    if player_lines:
        df_html = pd.DataFrame(player_lines)
        st.dataframe(df_html)

        output_html_excel = io.BytesIO()
        df_html.to_excel(output_html_excel, index=False, engine='openpyxl')
        output_html_excel.seek(0)
        st.download_button("⬇️ Scarica Excel giocatori/linee", data=output_html_excel, file_name="giocatori_linee.xlsx")

# 📥 Carica file Excel per analisi batch
st.subheader("📥 Carica file Excel per analisi batch")

metric_choice = st.radio("📊 Seleziona la metrica da analizzare", ["Punti", "Assist", "Rimbalzi", "P+A+R"], horizontal=True)

metric_map = {
    "Punti": "PTS",
    "Assist": "AST",
    "Rimbalzi": "REB",
    "P+A+R": "PAR"
}

uploaded_file = st.file_uploader("📁 Carica il file Excel con i giocatori e le linee", type=["xlsx"])

# Funzione per trovare il player_id normalizzando accenti, Jr., ecc.
def find_player_id(player_name):
    norm_input = unicodedata.normalize('NFKD', player_name).encode('ASCII', 'ignore').decode('utf-8').lower()
    all_players = players.get_players()

    for p in all_players:
        if unicodedata.normalize('NFKD', p['full_name']).encode('ASCII', 'ignore').decode('utf-8').lower() == norm_input:
            return p['id']

    for p in all_players:
        if norm_input in unicodedata.normalize('NFKD', p['full_name']).encode('ASCII', 'ignore').decode('utf-8').lower():
            return p['id']

    return None

if uploaded_file:
    input_df = pd.read_excel(uploaded_file)
    if 'Giocatore' in input_df.columns and 'Linea' in input_df.columns:
        st.success("File caricato correttamente! 🟢")
        results = []
        progress = st.progress(0)

        for i, row in input_df.iterrows():
            player_name = row['Giocatore']
            line = row['Linea']
            player_id = find_player_id(player_name)

            if player_id:
                time.sleep(0.6)
                logs = playergamelog.PlayerGameLog(player_id=player_id, season='2024-25', season_type_all_star='Regular Season')
                df_logs = logs.get_data_frames()[0]
                df_logs['PTS'] = pd.to_numeric(df_logs['PTS'], errors='coerce')
                df_logs['AST'] = pd.to_numeric(df_logs['AST'], errors='coerce')
                df_logs['REB'] = pd.to_numeric(df_logs['REB'], errors='coerce')
                df_logs['PAR'] = df_logs['PTS'] + df_logs['AST'] + df_logs['REB']

                values = df_logs[metric_map[metric_choice]].tolist()
                over_5 = sum(v > line for v in values[:5]) / 5 * 100
                over_10 = sum(v > line for v in values[:10]) / 10 * 100
                over_season = sum(v > line for v in values) / len(values) * 100 if values else 0

                results.append({
                    'Giocatore': player_name,
                    'Linea': line,
                    '% Over 5G': f"{over_5:.1f}%",
                    '% Over 10G': f"{over_10:.1f}%",
                    '% Over Stagione': f"{over_season:.1f}%"
                })
            else:
                results.append({
                    'Giocatore': player_name,
                    'Linea': line,
                    '% Over 5G': 'N/D',
                    '% Over 10G': 'N/D',
                    '% Over Stagione': 'N/D'
                })
            progress.progress((i + 1) / len(input_df))

        results_df = pd.DataFrame(results)
        st.dataframe(results_df)

        output_excel = io.BytesIO()
        results_df.to_excel(output_excel, index=False, engine='openpyxl')
        output_excel.seek(0)
        st.download_button("⬇️ Scarica risultati in Excel", data=output_excel, file_name="risultati_over.xlsx")
    else:
        st.error("❌ Il file deve contenere le colonne 'Giocatore' e 'Linea'.")

# 🔎 Ricerca giocatore singolo
st.subheader("🔍 Ricerca giocatore singolo")

player_name_input = st.text_input("🔍 Inserisci il nome del giocatore (es: LeBron James)")

if player_name_input:
    normalized_input = unicodedata.normalize('NFKD', player_name_input).encode('ASCII', 'ignore').decode('utf-8').lower()
    matched_players = [p for p in players.get_active_players() if normalized_input in unicodedata.normalize('NFKD', p['full_name']).encode('ASCII', 'ignore').decode('utf-8').lower()]

    if not matched_players:
        st.error("❌ Nessun giocatore trovato con questo nome.")
    else:
        selected_player = st.selectbox("✅ Scegli il giocatore corretto", matched_players, format_func=lambda p: p['full_name'])
        player_id = selected_player['id']

        metric = st.radio("📌 Scegli la metrica da visualizzare", ["Punti", "Assist", "Rimbalzi", "P+A+R"], horizontal=True)
        game_type = st.radio("🎯 Scegli il tipo di partita", ["Totale", "Casa", "Ospite"], horizontal=True)

        col_map = {
            "Punti": "PTS",
            "Assist": "AST",
            "Rimbalzi": "REB",
            "P+A+R": "PAR"
        }

        df = playergamelog.PlayerGameLog(player_id=player_id, season='2024-25', season_type_all_star='Regular Season').get_data_frames()[0]
        df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], errors='coerce')

        if metric == "P+A+R":
            df["PAR"] = df["PTS"] + df["AST"] + df["REB"]

        if game_type == "Casa":
            df = df[df['MATCHUP'].str.contains("vs")]
        elif game_type == "Ospite":
            df = df[df['MATCHUP'].str.contains("@")]

        col = col_map[metric]
        default_lines = {"PTS": 20.5, "AST": 5.5, "REB": 6.5, "PAR": 30.5}
        line = st.number_input(f"🎯 Inserisci la linea {metric.lower()}", min_value=0.0, max_value=100.0, value=default_lines[col], step=1.0)
        if line % 1 == 0:
            line += 0.5

        st.subheader("📈 Visualizza il grafico")
        chart_range = st.selectbox("Seleziona l'intervallo del grafico", ["Ultime 5", "Ultime 10", "Intera stagione"])

        if chart_range == "Ultime 5":
            df = df.head(5)
        elif chart_range == "Ultime 10":
            df = df.head(10)

        if not df.empty:
            fig, ax = plt.subplots(figsize=(10, 4))
            labels = df['GAME_DATE'].dt.strftime('%m/%d')
            colors = ['#00C853' if val > line else '#D50000' for val in df[col]]

            bars = ax.bar(labels, df[col], color=colors, width=0.6)
            for bar, val in zip(bars, df[col]):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{val:.0f}", ha='center', va='bottom', fontsize=9, color='white', weight='bold')

            ax.axhline(line, color='gray', linestyle='--', linewidth=1.5)
            ax.set_title(f"{selected_player['full_name']} - {metric}", fontsize=14, fontweight='bold')
            ax.set_ylabel(metric)
            ax.set_facecolor('#111111')
            fig.patch.set_facecolor('#111111')
            ax.tick_params(colors='white')
            st.pyplot(fig)

        st.subheader(f"📊 Statistiche {metric.lower()}")

        over_count = (df[col] > line).sum()
        total_count = len(df)
        pct = (over_count / total_count * 100) if total_count > 0 else 0
        st.write(f"**{selected_player['full_name']}** - **{pct:.1f}% over** ({over_count}/{total_count}) rispetto a linea {line}")
