import json
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="Crypto Volatility Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Crypto Volatility Dashboard")
st.caption("Experimental Version 1.0")

# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

TOKEN_SYMBOLS = [
    "SATS",
    "RATS",
    "MOG",
    "CAT",
    "FLOKI",
    "BONK",
    "PEPE",
    "SHIB"
]

CACHE_FILE = "coin_ids.json"

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

st.sidebar.header("Settings")

days = st.sidebar.selectbox(
    "Number of Days",
    [7, 14, 30],
    index=0
)

refresh_ids = st.sidebar.button("🔄 Refresh Coin IDs")

# ---------------------------------------------------------
# CACHE FUNCTIONS
# ---------------------------------------------------------

def load_cached_ids():

    file = Path(CACHE_FILE)

    if file.exists():
        with open(file, "r") as f:
            return json.load(f)

    return {}


def save_cached_ids(cache):

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)


# ---------------------------------------------------------
# SEARCH COINGECKO
# ---------------------------------------------------------

@st.cache_data(ttl=86400)
def search_coin(symbol):

    url = f"{COINGECKO_BASE}/search"

    r = requests.get(
        url,
        params={"query": symbol},
        timeout=20
    )

    r.raise_for_status()

    return r.json()


# ---------------------------------------------------------
# FIND CORRECT COIN ID
# ---------------------------------------------------------

def discover_coin_id(symbol):

    try:
        data = search_coin(symbol)
        coins = data.get("coins", [])

        if not coins:
            return None

        symbol = symbol.lower()

        # ---------- 1. Exact Symbol Match ----------
        exact_symbol = [
            coin for coin in coins
            if coin.get("symbol", "").lower() == symbol
        ]

        if exact_symbol:

            # Prefer highest ranked coin
            exact_symbol.sort(
                key=lambda x: (
                    x.get("market_cap_rank")
                    if x.get("market_cap_rank") is not None
                    else 999999
                )
            )

            return exact_symbol[0]["id"]

        # ---------- 2. Name Contains Symbol ----------
        name_match = [
            coin for coin in coins
            if symbol in coin.get("name", "").lower()
        ]

        if name_match:

            name_match.sort(
                key=lambda x: (
                    x.get("market_cap_rank")
                    if x.get("market_cap_rank") is not None
                    else 999999
                )
            )

            return name_match[0]["id"]

        # ---------- 3. First Search Result ----------
        return coins[0]["id"]

    except Exception as e:

        st.error(f"{symbol}: {e}")

        return None

# --------------------------------------------------------
# for Part 2
# ---------------------------------------------------------
# BINANCE SYMBOLS
# ---------------------------------------------------------

BINANCE_SYMBOLS = {
    "SATS": "1000SATSUSDT",
    "BONK": "BONKUSDT",
    "PEPE": "PEPEUSDT",
    "SHIB": "SHIBUSDT",
    "FLOKI": "FLOKIUSDT",
    "DOGS": "DOGSUSDT",
    "MOG": None,
    "RATS": None,
    "CAT": None
}
# --------------------------------------------------------

# ---------------------------------------------------------
# DOWNLOAD OHLC DATA
# ---------------------------------------------------------

@st.cache_data(ttl=600)
def download_binance_ohlc(symbol, days, show_ui=True):

    if symbol is None:
        return pd.DataFrame()

    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": "1d",
        "limit": days + 1
    }
    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        r = requests.get(url, params=params, headers=headers, timeout=20)
        st.write("Status Code:", r.status_code)
        st.write("URL:", r.url)
        st.write("Response:", r.text[:200])
        
        r.raise_for_status()
        candles = r.json()

    except Exception as e:
        st.error(f"{symbol}: {e}")
        return pd.DataFrame()

    rows = []

    for i in range(1, len(candles)):
        prev_close = float(candles[i-1][4])
        open_price = float(candles[i][1])
        high = float(candles[i][2])
        low = float(candles[i][3])
        close = float(candles[i][4])
        volume = float(candles[i][5])
        high_pct = ((high-prev_close)/prev_close)*100
        low_pct = ((low-prev_close)/prev_close)*100
        range_pct = ((high-low)/prev_close)*100

        rows.append({
            "Date": datetime.utcfromtimestamp(
                candles[i][0]/1000
            ).strftime("%Y-%m-%d"),
            "Previous Close": prev_close,
            "Open": open_price,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
            "High %": round(high_pct,2),
            "Low %": round(low_pct,2),
            "Range %": round(range_pct,2)
        })

    df = pd.DataFrame(rows)

    display_df = df.copy()
    price_cols = [
        "Previous Close",
        "Open",
        "High",
        "Low",
       "Close"
    ]

    for col in price_cols:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.10f}")

    display_df["Volume"] = display_df["Volume"].apply(lambda x: f"{x:,.0f}")

    percent_cols = ["High %", "Low %", "Range %"]

    for col in percent_cols:
        #display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%")
        display_df[col] = display_df[col].map(lambda x: f"{x:.2f}%")

    if show_ui:
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )


        metrics = calculate_volatility_metrics(df)

        if metrics is not None:

            st.subheader("Volatility Summary")

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Average Range",
                f"{metrics['Average Range %']:.2f}%"
            )

            col2.metric(
                "Maximum Range",
                f"{metrics['Maximum Range %']:.2f}%"
            )

            col3.metric(
                "Win Rate",
                f"{metrics['Win Rate']:.1f}%"
            )

            col4.metric(
                "Opportunity Score",
                f"{metrics['Opportunity Score']:.1f}"
            )

            summary = pd.DataFrame(
                metrics.items(),
                columns=["Metric", "Value"]
            )

        #if show_ui:
        st.dataframe(
            summary,
            use_container_width=True,
            hide_index=True
        )


    return df

# ---------------------------------------------------------

# --------------------------------------------------------
# -------------New function for volatility metrics -------

def calculate_volatility_metrics(df):

    if df.empty:
        return None

    metrics = {}

    # --------------------------
    # Average Movement
    # --------------------------
    metrics["Average High %"] = df["High %"].mean()
    metrics["Average Low %"] = df["Low %"].mean()
    metrics["Average Range %"] = df["Range %"].mean()

    # --------------------------
    # Maximum / Minimum
    # --------------------------
    metrics["Maximum Range %"] = df["Range %"].max()
    metrics["Minimum Range %"] = df["Range %"].min()

    # --------------------------
    # Standard Deviation
    # --------------------------
    metrics["Std Deviation"] = df["Range %"].std()

    # --------------------------
    # Median
    # --------------------------
    metrics["Median Range %"] = df["Range %"].median()

    # --------------------------
    # Average Volume
    # --------------------------
    metrics["Average Volume"] = df["Volume"].mean()

    # --------------------------
    # Opportunity Days
    # --------------------------
    metrics["Days > 5%"] = (df["Range %"] >= 5).sum()
    metrics["Days > 10%"] = (df["Range %"] >= 10).sum()
    metrics["Days > 15%"] = (df["Range %"] >= 15).sum()
    metrics["Days > 20%"] = (df["Range %"] >= 20).sum()

    # --------------------------
    # Positive Close Days
    # --------------------------
    metrics["Green Days"] = (df["Close"] > df["Previous Close"]).sum()
    metrics["Red Days"] = (df["Close"] < df["Previous Close"]).sum()

    # --------------------------
    # Win Rate
    # --------------------------
    metrics["Win Rate"] = (
        metrics["Green Days"] / len(df)
    ) * 100

    # --------------------------
    # Opportunity Score
    # --------------------------

    score = (
        metrics["Average Range %"] * 2
        + metrics["Days > 10%"] * 3
        + metrics["Days > 20%"] * 5
    )
    metrics["Opportunity Score"] = round(score, 2)

    return metrics
# --------------------------------------------------------

# ========================================================
# Compare all tokens
# --------------------------------------------------------
def compare_all_tokens(days):

    results = []
    for token, symbol in BINANCE_SYMBOLS.items():

        if symbol is None:
            continue

        try:

            df = download_binance_ohlc(symbol, days, show_ui=False)
            if df.empty:
                continue
            metrics = calculate_volatility_metrics(df)
            results.append({
                "Token": token,
                "Average Range %":
                    round(metrics["Average Range %"],2),
                "Maximum Range %":
                    round(metrics["Maximum Range %"],2),
                "Minimum Range %":
                    round(metrics["Minimum Range %"],2),
                "Std Dev":
                    round(metrics["Std Deviation"],2),
                "Win Rate":
                    round(metrics["Win Rate"],1),
                "Opportunity Score":
                    round(metrics["Opportunity Score"],1),
                "Average Volume":
                    round(metrics["Average Volume"], 0),
            })

        except Exception as e:
            st.warning(f"{token}: {e}")

    return pd.DataFrame(results)
# ----------------------------------------------------------

# ----------------------------------------------------------
# Assign grade
def assign_grade(score):

    if score >= 90:
        return "A+"

    elif score >= 80:
        return "A"

    elif score >= 70:
        return "B+"

    elif score >= 60:
        return "B"

    elif score >= 50:
        return "C"

    return "D"
# ----------------------------------------------------------

# ----------------------------------------------------------
# Professional Scanner
def professional_scanner(df):

    df = df.copy()

    max_range = df["Average Range %"].max()
    max_volume = df["Opportunity Score"].max()
    
    max_avg_volume = df["Average Volume"].max()

    max_opportunity = df["Opportunity Score"].max()


    scanner = []

    for _, row in df.iterrows():

        # -------------------------
        # Volatility
        # -------------------------

        volatility = (
            row["Average Range %"] /
            max_range
        ) * 30

        # -------------------------
        # Consistency
        # -------------------------

        consistency = max(
            0,
            20 - row["Std Dev"]
        )

        # -------------------------
        # Liquidity
        # -------------------------

        #liquidity = (
        #    row["Opportunity Score"] /
        #    max_volume
        #) * 20

        liquidity = (
            row["Average Volume"] /
            max_avg_volume
        ) * 20


        # -------------------------
        # Win Rate
        # -------------------------

        win = (
            row["Win Rate"] / 100
        ) * 15

        # -------------------------
        # Opportunity
        # -------------------------

        #opportunity = (
        #    row["Opportunity Score"] /
        #    max_volume
        #) * 15

        opportunity = (
            row["Opportunity Score"] /
            max_opportunity
        ) * 15

        total = (
            volatility +
            consistency +
            liquidity +
            win +
            opportunity
        )


        scanner.append({

            "Token":
                row["Token"],

            "Volatility":
                round(volatility,1),

            "Consistency":
                round(consistency,1),

            "Liquidity":
                round(liquidity,1),

            "Win":
                round(win,1),

            "Opportunity":
                round(opportunity,1),

            "Total Score":
                round(total,1),

            "Grade":
                assign_grade(total)

        })

    return pd.DataFrame(scanner)
# ---------------------------------------------------------

# ---------------------------------------------------------
# LOAD IDS
# ---------------------------------------------------------

coin_ids = load_cached_ids()

if refresh_ids:
    coin_ids = {}

progress = st.progress(0)
status = st.empty()

for i, symbol in enumerate(TOKEN_SYMBOLS):
    progress.progress((i + 1) / len(TOKEN_SYMBOLS))
    status.write(f"Searching {symbol}...")

    if symbol not in coin_ids:
        coin_id = discover_coin_id(symbol)

        if coin_id:
            coin_ids[symbol] = coin_id
            save_cached_ids(coin_ids)

        time.sleep(1.3)

progress.empty()
status.empty()
# ---------------------------------------------------------

# ---------------------------------------------------------
# DOWNLOAD DATA
# ---------------------------------------------------------

st.header("Historical Data")

selected_token = st.selectbox(
    "Select Token",
    list(BINANCE_SYMBOLS.keys())
)

df = download_binance_ohlc(
    BINANCE_SYMBOLS[selected_token],
    days, show_ui=True
)

if df.empty:
    st.warning("No Binance data available.")

# st.success("Part 1 completed successfully.")
st.divider()
st.header("🏆 Multi Token Comparison")
comparison_df = compare_all_tokens(days)
st.write(comparison_df)
comparison_df = comparison_df.sort_values(
    by="Opportunity Score",
    ascending=False
)
comparison_df.insert(
    0,
    "Rank",
    range(1, len(comparison_df)+1)
)
display = comparison_df.copy()

display["Average Range %"] = \
display["Average Range %"].map(lambda x:f"{x:.2f}%")

display["Maximum Range %"] = \
display["Maximum Range %"].map(lambda x:f"{x:.2f}%")

display["Minimum Range %"] = \
display["Minimum Range %"].map(lambda x:f"{x:.2f}%")

display["Std Dev"] = \
display["Std Dev"].map(lambda x:f"{x:.2f}")

display["Win Rate"] = \
display["Win Rate"].map(lambda x:f"{x:.1f}%")

#if show_ui:
st.dataframe(
    display,
    hide_index=True,
    use_container_width=True
)

if not comparison_df.empty:

    winner = comparison_df.iloc[0]
    st.success(
        f"🏆 Best Trading Opportunity : "
        f"{winner['Token']} "
        f"(Score {winner['Opportunity Score']})"
    )
else:
    st.warning("No comparison data available.")

st.divider()
st.header("⭐ Professional Volatility Scanner")
scanner_df = professional_scanner(comparison_df)
scanner_df = scanner_df.sort_values(
    by="Total Score",
    ascending=False
)
scanner_df.insert(
    0,
    "Rank",
    range(1, len(scanner_df)+1)
)
st.dataframe(
    scanner_df,
    use_container_width=True,
    hide_index=True
)



fig = px.bar(
    comparison_df,
    x="Token",
    y="Opportunity Score",
    text="Opportunity Score",
    title="Opportunity Score Ranking"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

fig2 = px.bar(
    comparison_df,
    x="Token",
    y="Average Range %",
    text="Average Range %",
    title="Average Daily Range"
)

st.plotly_chart(
    fig2,
    use_container_width=True
)

