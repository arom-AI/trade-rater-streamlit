import streamlit as st
import pandas as pd
from datetime import datetime, date

import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Trade Rater %", layout="centered")

# Petit polish visuel léger
st.markdown("""
<style>
    .main {padding-top: 1.5rem;}
    h1 {font-size: 2.3rem;}
    .stButton>button {
        border-radius: 0.5rem;
        padding: 0.4rem 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Trade Rater — Score en % (version biais Romu, Sheets)")

# ──────────────────────────────
# Connexion Google Sheets
# ──────────────────────────────
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_worksheet():
    # infos du compte de service
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPE)
    client = gspread.authorize(creds)

    # gsheet_id stocké dans la même section
    gsheet_id = st.secrets["gcp_service_account"]["gsheet_id"]

    sh = client.open_by_key(gsheet_id)
    ws = sh.sheet1

    # S'assurer que l'en-tête existe
    header = ws.row_values(1)
    expected = [
        "datetime","date_trade","pair","direction","timeframe",
        "session","rr","score_percent","commentaire","taken","result"
    ]
    if header != expected:
        ws.clear()
        ws.append_row(expected)
    return ws


ws = get_worksheet()

def append_trade(row_dict: dict):
    """Ajoute un trade en fin de feuille."""
    row = [
        row_dict.get("datetime", ""),
        row_dict.get("date_trade", ""),
        row_dict.get("pair", ""),
        row_dict.get("direction", ""),
        row_dict.get("timeframe", ""),
        row_dict.get("session", ""),
        row_dict.get("rr", ""),
        row_dict.get("score_percent", ""),
        row_dict.get("commentaire", ""),
        row_dict.get("taken", ""),
        row_dict.get("result", ""),
    ]
    ws.append_row(row)

def load_all_trades() -> pd.DataFrame:
    """Charge tous les trades depuis Sheets dans un DataFrame."""
    values = ws.get_all_values()
    if len(values) <= 1:
        return pd.DataFrame(columns=[
            "datetime","date_trade","pair","direction","timeframe",
            "session","rr","score_percent","commentaire","taken","result","sheet_row"
        ])
    header = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)
    # Ajouter index de ligne réelle dans la feuille (1 = header)
    df["sheet_row"] = df.index + 2

    # Types
    if "date_trade" in df.columns:
        df["date_trade"] = pd.to_datetime(df["date_trade"], errors="coerce").dt.date
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    for col in ["rr", "score_percent"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

def update_taken_and_result(updates):
    """
    updates = list of dict: {"sheet_row": int, "taken": str, "result": str}
    """
    header = ws.row_values(1)
    col_taken = header.index("taken") + 1
    col_result = header.index("result") + 1
    for u in updates:
        r = int(u["sheet_row"])
        if u.get("taken") is not None:
            ws.update_cell(r, col_taken, u["taken"])
        if u.get("result") is not None:
            ws.update_cell(r, col_result, u["result"])

# ──────────────────────────────
# UI
# ──────────────────────────────

mode = st.sidebar.selectbox(
    "Mode",
    ["Nouveau trade", "Dashboard hebdo"]
)

# =========================================================
# MODE 1 : NOUVEAU TRADE
# =========================================================
if mode == "Nouveau trade":

    st.write("Remplis les critères de ton setup, et je calcule un pourcentage de qualité (peut dépasser 100%).")

    # --- Infos générales ---
    st.subheader("Infos générales")

    col1, col2 = st.columns(2)
    with col1:
        date_trade = st.date_input("Date du trade", value=datetime.now())
        pair = st.text_input("Instrument (ex: XAUUSD, US30, EURUSD)", value="XAUUSD")
        direction = st.selectbox("Direction", ["Buy", "Sell"])
    with col2:
        timeframe = st.selectbox("Timeframe d'entrée", ["M1", "M5", "M15", "M30", "H1", "H2", "H4"])
        rr = st.number_input("Risque / Reward (ex: 3 pour 1:3)", min_value=0.1, step=0.1, value=3.0)
        plan_respecte = st.selectbox(
            "Lien avec ton plan de début de semaine",
            [
                "Hors plan / improvisé",
                "Dans une paire intéressante mais pas setup principal",
                "Pile dans le scénario principal du plan"
            ]
        )

    screenshot = st.file_uploader("Screenshot du chart (optionnel)", type=["png", "jpg", "jpeg"])

    score = 0
    notes = []

    # --- A. Contexte HTF ---
    st.subheader("A. Contexte HTF (H4 / Daily / Weekly)")

    sync_option = st.selectbox(
        "Quels timeframes sont alignés (bullish ou bearish) ?",
        [
            "Aucun vraiment aligné",
            "H4 + Daily alignés",
            "Daily + Weekly alignés",
            "H4 + Daily + Weekly alignés"
        ]
    )

    if sync_option == "Aucun vraiment aligné":
        score += 0
        notes.append("Contexte HTF pas aligné (0)")
    elif sync_option == "H4 + Daily alignés":
        score += 10
        notes.append("H4 + Daily alignés (+10)")
    elif sync_option == "Daily + Weekly alignés":
        score += 15
        notes.append("Daily + Weekly alignés (+15)")
    elif sync_option == "H4 + Daily + Weekly alignés":
        score += 20
        notes.append("H4 + Daily + Weekly alignés (+20)")

    # --- B. AOI ---
    st.subheader("B. Zone d'intérêt (AOI)")

    aoi_choice = st.selectbox(
        "Où se situe le trade par rapport à tes AOI Daily / Weekly ?",
        [
            "Pas vraiment sur une AOI",
            "Sur une AOI Daily uniquement",
            "Sur une AOI Weekly uniquement",
            "Sur une AOI alignée Daily + Weekly (même zone)"
        ]
    )

    if aoi_choice == "Pas vraiment sur une AOI":
        score += 0
        notes.append("Pas sur une AOI (0)")
    elif aoi_choice == "Sur une AOI Daily uniquement":
        score += 10
        notes.append("Sur AOI Daily (+10)")
    elif aoi_choice == "Sur une AOI Weekly uniquement":
        score += 15
        notes.append("Sur AOI Weekly (+15)")
    elif aoi_choice == "Sur une AOI alignée Daily + Weekly (même zone)":
        score += 20
        notes.append("AOI Daily + Weekly alignées (+20)")

    aoi_recent = st.selectbox(
        "Le prix a-t-il touché une AOI récemment (sans forcément s'y installer) ?",
        ["Non", "Oui"]
    )
    if aoi_recent == "Oui":
        score += 5
        notes.append("Touché AOI récemment (+5)")

    # --- C. Pattern & entrée ---
    st.subheader("C. Pattern Head & Shoulders / Entrée")

    hs_quality = st.selectbox(
        "Qualité du pattern Head & Shoulders (dans le sens du trade)",
        [
            "Pas vraiment un H&S",
            "H&S présent mais pas super clean",
            "H&S très propre"
        ]
    )

    neckline_break = st.selectbox(
        "Cassure de la neckline",
        [
            "Cassure molle / discutable",
            "Cassure nette avec impulsion"
        ]
    )

    neckline_retest = st.selectbox(
        "Retest de la neckline",
        [
            "Pas de vrai retest",
            "Retest clair de la neckline"
        ]
    )

    cont_pattern = st.selectbox(
        "Continuation pattern pour l'entrée (tes patterns de continuation)",
        [
            "Pas de pattern clair",
            "Pattern présent mais moyen",
            "Pattern de continuation très propre"
        ]
    )

    # H&S
    if hs_quality == "Pas vraiment un H&S":
        score += 0
    elif hs_quality == "H&S présent mais pas super clean":
        score += 10
        notes.append("H&S correct (+10)")
    elif hs_quality == "H&S très propre":
        score += 15
        notes.append("H&S très propre (+15)")

    # Cassure neckline
    if neckline_break == "Cassure molle / discutable":
        score += 3
        notes.append("Cassure moyenne (+3)")
    else:
        score += 5
        notes.append("Cassure nette (+5)")

    # Retest
    if neckline_retest == "Retest clair de la neckline":
        score += 3
        notes.append("Retest (+3)")

    # Pattern de continuation
    if cont_pattern == "Pattern présent mais moyen":
        score += 3
        notes.append("Pattern de continuation moyen (+3)")
    elif cont_pattern == "Pattern de continuation très propre":
        score += 5
        notes.append("Pattern de continuation très propre (+5)")

    # --- D. Confluences ---
    st.subheader("D. Confluences & exécution")

    ema50_align = st.selectbox(
        "Alignement avec l'EMA 50 (selon les timeframes)",
        [
            "Contre EMA 50 sur la plupart des TF",
            "Aligné seulement sur la TF d'entrée (≤ M30)",
            "Aligné sur H1",
            "Aligné sur H4 ou TF plus haute",
            "Aligné sur plusieurs TF (entrée + H1/H4)"
        ]
    )

    if ema50_align == "Contre EMA 50 sur la plupart des TF":
        score -= 5
        notes.append("Contre EMA 50 globalement (-5)")
    elif ema50_align == "Aligné seulement sur la TF d'entrée (≤ M30)":
        score += 3
        notes.append("EMA 50 alignée seulement sur la TF d'entrée (+3)")
    elif ema50_align == "Aligné sur H1":
        score += 5
        notes.append("EMA 50 alignée sur H1 (+5)")
    elif ema50_align == "Aligné sur H4 ou TF plus haute":
        score += 8
        notes.append("EMA 50 alignée sur H4 / HTF (+8)")
    elif ema50_align == "Aligné sur plusieurs TF (entrée + H1/H4)":
        score += 10
        notes.append("EMA 50 alignée sur plusieurs TF (+10)")

    # RR
    if rr < 2:
        notes.append("RR < 1:2 (0)")
    elif 2 <= rr < 3:
        score += 5
        notes.append("RR correct (+5)")
    else:
        score += 10
        notes.append("RR excellent (+10)")

    # Plan
    if plan_respecte == "Hors plan / improvisé":
        score += 0
        notes.append("Hors plan (0)")
    elif plan_respecte == "Dans une paire intéressante mais pas setup principal":
        score += 10
        notes.append("Dans une paire intéressante (+10)")
    else:
        score += 20
        notes.append("Dans le scénario du plan (+20)")

    # --- E. Session ---
    st.subheader("E. Session")

    session = st.selectbox("Session du trade", ["Tokyo", "Sydney", "London", "New York", "Autre"])

    session_bonus = 0
    pair_upper = pair.upper()

    if session in ["London", "New York"]:
        session_bonus = 5
        notes.append(f"Session {session} (+5)")
    elif session in ["Tokyo", "Sydney"]:
        if "JPY" in pair_upper and session == "Tokyo":
            session_bonus = 0
            notes.append("Tokyo OK pour JPY (0)")
        elif ("AUD" in pair_upper or "NZD" in pair_upper) and session == "Sydney":
            session_bonus = 0
            notes.append("Sydney OK pour AUD/NZD (0)")
        else:
            session_bonus = -5
            notes.append(f"Session {session} (-5)")

    score += session_bonus

    # --- F. Market structure HTF ---
    st.subheader("F. Market structure HTF")

    ms_htf = st.slider(
        "La structure de marché HTF (H4/Daily/Weekly) est-elle propre et alignée avec ton trade ?",
        0, 5, 0
    )
    score += ms_htf
    if ms_htf > 0:
        notes.append(f"Market structure HTF alignée (+{ms_htf})")

    # --- Résultat + AUTO-REFUS ---
    st.subheader("Résultat")

    score_percent = score

    st.metric("Qualité du setup", f"{score_percent:.1f} %")

    if score_percent < 80:
        st.error("❌ NO TRADE — Score < 80%. Le plan dit NON.")
    else:
        st.success("✅ Trade potentiellement acceptable selon le plan (≥ 80%).")

    st.write("Notes :")
    for n in notes:
        st.write("- " + n)

    commentaire = st.text_area("Commentaire perso (facultatif)")

    # Choix par défaut : trade pris ? (tu peux modifier plus tard dans le dashboard)
    taken_default = st.selectbox("As-tu pris ce trade ?", ["Non", "Oui"], index=0)
    result_default = st.selectbox(
        "Résultat (tu pourras le corriger plus tard)",
        ["Non pris", "Win", "Loss", "BE"],
        index=0
    )

    # --- Sauvegarde ---
    if st.button("Enregistrer le trade"):
        row = {
            "datetime": datetime.now().isoformat(timespec="seconds"),
            "date_trade": date_trade.isoformat(),
            "pair": pair,
            "direction": direction,
            "timeframe": timeframe,
            "session": session,
            "rr": rr,
            "score_percent": score_percent,
            "commentaire": commentaire,
            "taken": taken_default,
            "result": result_default,
        }
        append_trade(row)
        st.success("✅ Trade enregistré dans Google Sheets")

# =========================================================
# MODE 2 : DASHBOARD HEBDO
# =========================================================
else:
    st.subheader("📅 Dashboard hebdo — scores & ranking")

    df = load_all_trades()
    if df.empty:
        st.warning("Aucun trade enregistré pour l’instant.")
        st.stop()

    iso_calendar = pd.to_datetime(df["date_trade"]).map(lambda d: d.isocalendar())
    df["iso_year"] = [x.year for x in iso_calendar]
    df["iso_week"] = [x.week for x in iso_calendar]

    today = date.today()
    current_iso = today.isocalendar()
    current_year, current_week = current_iso.year, current_iso.week

    weeks_available = (
        df[["iso_year", "iso_week"]]
        .drop_duplicates()
        .sort_values(["iso_year", "iso_week"], ascending=[False, False])
    )

    weeks_labels = [
        f"{int(row.iso_year)}-W{int(row.iso_week)}"
        for _, row in weeks_available.iterrows()
    ]

    default_label = f"{current_year}-W{current_week}"
    default_index = weeks_labels.index(default_label) if default_label in weeks_labels else 0

    selected_label = st.selectbox(
        "Choisis la semaine (année-ISOsemaine)",
        weeks_labels,
        index=default_index
    )

    sel_year, sel_week = selected_label.split("-W")
    sel_year = int(sel_year)
    sel_week = int(sel_week)

    df_week = df[(df["iso_year"] == sel_year) & (df["iso_week"] == sel_week)]

    if df_week.empty:
        st.info("Aucun trade pour cette semaine.")
        st.stop()

    st.write(f"Trades pour la semaine {sel_year}-W{sel_week} : {len(df_week)} trade(s).")

    # Ranking
    st.subheader("🏆 Ranking des trades (par score)")

    df_sorted = df_week.sort_values("score_percent", ascending=False).reset_index(drop=True)

    updates = []

    for idx, row in df_sorted.iterrows():
        st.markdown(f"### {idx+1}. {row['date_trade']} — {row['pair']} {row['direction']} "
                    f"({row['timeframe']} / {row['session']}) → **{row['score_percent']:.1f}%**")

        st.write(f"Pris : {row.get('taken', '')} | Résultat : {row.get('result', '')}")

        # Widgets d’édition
        col1, col2 = st.columns(2)
        with col1:
            taken_new = st.selectbox(
                f"Pris ? (trade {idx+1})",
                ["", "Oui", "Non"],
                index=["", "Oui", "Non"].index(row["taken"]) if row["taken"] in ["Oui", "Non"] else 0,
                key=f"taken_{row['sheet_row']}"
            )
        with col2:
            result_new = st.selectbox(
                f"Résultat (trade {idx+1})",
                ["", "Win", "Loss", "BE", "Non pris"],
                index=["", "Win", "Loss", "BE", "Non pris"].index(row["result"]) if row["result"] in ["Win", "Loss", "BE", "Non pris"] else 0,
                key=f"result_{row['sheet_row']}"
            )

        updates.append({
            "sheet_row": row["sheet_row"],
            "taken": taken_new if taken_new != "" else None,
            "result": result_new if result_new != "" else None,
        })

        if isinstance(row.get("commentaire", ""), str) and row["commentaire"].strip():
            st.write(f"💬 _{row['commentaire']}_")
        st.write("---")

    if st.button("💾 Enregistrer les modifications (pris / résultat)"):
        update_taken_and_result(updates)
        st.success("✅ Modifications enregistrées dans Google Sheets (recharge la page pour voir à jour).")

    # Histogramme
    st.subheader("📊 Distribution des scores")

    chart_df = df_sorted[["datetime", "score_percent"]].copy()
    chart_df = chart_df.set_index("datetime")

    st.bar_chart(chart_df, y="score_percent")

    # Stats
    st.subheader("📈 Stats rapides")

    moyenne = df_week["score_percent"].mean()
    max_score = df_week["score_percent"].max()
    min_score = df_week["score_percent"].min()

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Score moyen", f"{moyenne:.1f} %")
    col_b.metric("Meilleur score", f"{max_score:.1f} %")
    col_c.metric("Pire score", f"{min_score:.1f} %")
