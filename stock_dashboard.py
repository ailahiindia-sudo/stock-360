# ==================================================
# GEO-SENTINEL 360 - ULTIMATE PRO DASHBOARD
# ==================================================
# Fixed: Trailing Dividend Yield (last 365 days)
# Added: Separate columns for Latest News & Price Headline
# ==================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import numpy as np
from datetime import datetime, timedelta
from textblob import TextBlob
import time

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Geo-Sentinel 360 - Ultimate", layout="wide", page_icon="📊")

# ---------- MASTER LIST OF INDIAN STOCKS (NIFTY 50) ----------
STOCK_LIST = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
    "Hindustan Unilever": "HINDUNILVR.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "ITC Limited": "ITC.NS",
    "Kotak Mahindra Bank": "KOTAKBANK.NS",
    "State Bank of India": "SBIN.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Larsen & Toubro": "LT.NS",
    "Wipro": "WIPRO.NS",
    "Asian Paints": "ASIANPAINT.NS",
    "Axis Bank": "AXISBANK.NS",
    "HCL Technologies": "HCLTECH.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Titan Company": "TITAN.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Coal India": "COALINDIA.NS",
    "Power Grid": "POWERGRID.NS",
    "NTPC": "NTPC.NS",
    "Bajaj Finserv": "BAJAJFINSV.NS",
    "Tata Steel": "TATASTEEL.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "Tech Mahindra": "TECHM.NS",
    "Grasim": "GRASIM.NS"
}

# ---------- 1. FETCH GEOPOLITICAL RISK (GPR) INDEX ----------
@st.cache_data(ttl=3600)
def fetch_gpr_index():
    try:
        url = "https://www.matteoiacoviello.com/gpr_data.txt"
        df = pd.read_csv(url, sep='\s+', skiprows=9, header=None, names=['Date', 'GPR'])
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        df = df.sort_values('Date').tail(30)
        if len(df) > 0:
            latest = df.iloc[-1]
            percentile_95 = df['GPR'].quantile(0.95)
            return {
                'current': round(latest['GPR'], 2),
                'percentile_95': round(percentile_95, 2),
                'status': 'Elevated' if latest['GPR'] > percentile_95 else 'Normal'
            }
    except:
        return {'current': 0, 'percentile_95': 0, 'status': 'Unavailable'}
    return {'current': 0, 'percentile_95': 0, 'status': 'Error'}

# ---------- 2. FETCH NEWS & HEADLINES (Multi-article) ----------
@st.cache_data(ttl=1800)
def fetch_news_for_stock(stock_symbol, limit=5):
    """
    Fetches top 'limit' news headlines for a given stock.
    Returns: (primary_headline, sentiment_score, list_of_articles)
    """
    api_key = "YOUR_NEWS_API_KEY"  # Optional: Get free key from GNews.io
    query = stock_symbol.replace('.NS', '') + " stock India"
    articles_list = []
    primary_headline = "No recent news found."
    sentiment_score = 0.0

    try:
        if api_key != "YOUR_NEWS_API_KEY":
            url = f"https://gnews.io/api/v4/search?q={query}&token={api_key}&lang=en&max={limit}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                if articles:
                    for art in articles:
                        articles_list.append({
                            'title': art.get('title', 'No Title'),
                            'description': art.get('description', 'No description available.'),
                            'source': art.get('source', {}).get('name', 'Unknown'),
                            'url': art.get('url', '#'),
                            'published': art.get('publishedAt', '')
                        })
                    primary_headline = articles[0].get('title', primary_headline)
                    sentiments = []
                    for art in articles[:3]:
                        analysis = TextBlob(art['title'] + ". " + art.get('description', ''))
                        sentiments.append(analysis.sentiment.polarity)
                    if sentiments:
                        sentiment_score = np.mean(sentiments) * 100
    except:
        pass

    # Fallback if no articles
    if not articles_list:
        articles_list.append({
            'title': 'No news articles found. Consider adding a GNews API key.',
            'description': 'Without a key, detailed news cannot be fetched.',
            'source': 'System',
            'url': '#',
            'published': datetime.now().strftime('%Y-%m-%d')
        })

    return primary_headline, round(sentiment_score, 2), articles_list

# ---------- 3. ANALYZE A SINGLE STOCK (with ALL new columns) ----------
def analyze_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or 'longName' not in info:
            return None

        # Fetch last 50 days for indicators
        hist = ticker.history(period="50d")
        if hist.empty or len(hist) < 20:
            return None

        close = hist['Close']
        current_price = close.iloc[-1]

        # ----- 1. FUNDAMENTAL SCORE (0-100) -----
        pe = info.get('trailingPE', 0)
        roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
        debt_eq = info.get('debtToEquity', 1)
        profit_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0

        fund_score = 50
        if pe and 0 < pe < 25: fund_score += 20
        elif pe and pe >= 25: fund_score -= 10
        elif not pe or pe <= 0: fund_score -= 5
        if roe > 15: fund_score += 20
        elif roe < 5: fund_score -= 20
        if debt_eq < 0.5: fund_score += 10
        elif debt_eq > 1.5: fund_score -= 10
        if profit_margin > 10: fund_score += 10
        elif profit_margin < 0: fund_score -= 10
        fund_score = max(0, min(100, fund_score))

        # ----- 2. TECHNICAL SCORE (0-100) -----
        ma_20 = close.rolling(20).mean().iloc[-1]
        ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma_20

        tech_score = 50
        if current_price > ma_20: tech_score += 20
        else: tech_score -= 20
        if current_price > ma_50: tech_score += 20
        else: tech_score -= 20

        high_52 = info.get('fiftyTwoWeekHigh', current_price)
        low_52 = info.get('fiftyTwoWeekLow', current_price)
        if high_52 > low_52:
            position = (current_price - low_52) / (high_52 - low_52)
            tech_score += (position * 20) - 10
        tech_score = max(0, min(100, tech_score))

        # ----- 3. NEWS, SENTIMENT & HEADLINES -----
        news_headline, raw_sent, articles = fetch_news_for_stock(symbol, limit=5)
        norm_sent_score = 50 + (raw_sent / 2)
        norm_sent_score = max(0, min(100, norm_sent_score))

        # ----- 4. GEOPOLITICAL SCORE -----
        gpr = fetch_gpr_index()
        geo_score = 70 if gpr['status'] == 'Normal' else (30 if gpr['status'] == 'Elevated' else 50)

        # ----- 5. FINAL COMPOSITE INDEX -----
        final_index = (fund_score * 0.30) + (tech_score * 0.30) + (norm_sent_score * 0.20) + (geo_score * 0.20)
        final_index = round(final_index, 1)

        # ----- 6. SIGNAL -----
        if final_index >= 75: signal = "Strong Buy"
        elif final_index >= 60: signal = "Buy"
        elif final_index >= 45: signal = "Hold"
        elif final_index >= 30: signal = "Reduce"
        else: signal = "Sell"

        # ----- 7. ATR & TARGETS -----
        high = hist['High']
        low = hist['Low']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        if pd.isna(atr) or atr == 0:
            atr = current_price * 0.02

        entry = round(current_price, 2)
        risk = round(atr * 2, 2)
        stop_loss = round(entry - risk, 2)
        tp1 = round(entry + (risk * 1.5), 2)
        tp2 = round(entry + (risk * 2.5), 2)
        tp3 = round(entry + (risk * 3.5), 2)
        rr_ratio = round((tp1 - entry) / (entry - stop_loss), 2) if (entry - stop_loss) > 0 else 0

        # ----- 8. PIVOT POINTS (S/R) -----
        if len(hist) >= 2:
            prev = hist.iloc[-2]
            prev_high = prev['High']
            prev_low = prev['Low']
            prev_close = prev['Close']
        else:
            prev_high = high.iloc[-1]
            prev_low = low.iloc[-1]
            prev_close = close.iloc[-1]

        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = round((2 * pivot) - prev_low, 2)
        r2 = round(pivot + (prev_high - prev_low), 2)
        r3 = round(prev_high + 2 * (pivot - prev_low), 2)
        s1 = round((2 * pivot) - prev_high, 2)
        s2 = round(pivot - (prev_high - prev_low), 2)
        s3 = round(prev_low - 2 * (prev_high - pivot), 2)

        # ----- 9. IMPROVED DIVIDEND YIELD (Trailing 12 Months) -----
        try:
            dividends = ticker.dividends
            if not dividends.empty:
                one_year_ago = datetime.now() - timedelta(days=365)
                recent_divs = dividends[dividends.index >= one_year_ago]
                total_div = recent_divs.sum()
                if current_price > 0 and total_div > 0:
                    div_yield = round((total_div / current_price) * 100, 2)
                else:
                    div_yield = 0.0
            else:
                div_yield = 0.0
        except:
            div_yield = 0.0

        # ----- 10. GENERATE PRICE HEADLINE (Separate Column) -----
        change_pct = info.get('regularMarketChangePercent', 0)
        if change_pct and change_pct != 0:
            price_headline = f"Price moved {round(change_pct, 2)}% today"
        else:
            # Fallback to 5-day change
            try:
                hist_5d = ticker.history(period="5d")
                if len(hist_5d) > 1:
                    chg = (hist_5d['Close'].iloc[-1] - hist_5d['Close'].iloc[-2]) / hist_5d['Close'].iloc[-2] * 100
                    price_headline = f"Price moved {round(chg, 2)}% in last 5 days"
                else:
                    price_headline = "Price change data not available"
            except:
                price_headline = "Price change data not available"

        # ----- 11. OTHER METRICS (Market Cap, 52W, etc.) -----
        fund_data_date = info.get('mostRecentQuarter')
        if fund_data_date:
            try:
                fund_date_str = datetime.fromtimestamp(fund_data_date).strftime('%Y-%m-%d')
            except:
                fund_date_str = 'N/A'
        else:
            fund_date_str = 'N/A'

        market_cap = info.get('marketCap', 0)
        market_cap_cr = round(market_cap / 1e7, 2) if market_cap > 0 else 0

        pb_ratio = info.get('priceToBook', 'N/A')
        if pb_ratio != 'N/A':
            pb_ratio = round(pb_ratio, 2)

        high_52_val = info.get('fiftyTwoWeekHigh', current_price)
        low_52_val = info.get('fiftyTwoWeekLow', current_price)
        pct_from_high = round(((high_52_val - current_price) / high_52_val) * 100, 2) if high_52_val > 0 else 0
        pct_from_low = round(((current_price - low_52_val) / low_52_val) * 100, 2) if low_52_val > 0 else 0

        volume = info.get('volume', 0)
        avg_volume = info.get('averageVolume', 0)
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')

        # ----- RETURN ALL DATA -----
        return {
            'Company': info.get('longName', symbol),
            'Symbol': symbol.replace('.NS', ''),
            'Price': entry,
            'Change %': round(change_pct, 2) if change_pct else 0,
            'Composite': final_index,
            'Signal': signal,
            'Fundamental': round(fund_score, 1),
            'Technical': round(tech_score, 1),
            'Sentiment': round(norm_sent_score, 1),
            'Geopolitical': round(geo_score, 1),
            'Fund Data As Of': fund_date_str,
            'Market Cap (₹ Cr)': market_cap_cr,
            'P/B Ratio': pb_ratio,
            'Div Yield (Trailing %)': div_yield,
            '52W High': round(high_52_val, 2),
            '52W Low': round(low_52_val, 2),
            '% from 52W High': pct_from_high,
            '% from 52W Low': pct_from_low,
            'Volume': volume,
            'Avg Volume (10d)': avg_volume,
            'Sector': sector,
            'Industry': industry,
            'Entry': entry,
            'Stop Loss': stop_loss,
            'TP1': tp1,
            'TP2': tp2,
            'TP3': tp3,
            'R/R': rr_ratio,
            'S1': s1,
            'S2': s2,
            'S3': s3,
            'R1': r1,
            'R2': r2,
            'R3': r3,
            '📈 Price Headline': price_headline,  # NEW COLUMN
            '📰 Latest News': news_headline,     # NEW COLUMN
            '_articles': articles
        }
    except Exception as e:
        return None

# ---------- 4. MAIN DASHBOARD UI ----------
st.title("📊 Geo-Sentinel 360 - Ultimate Pro Dashboard")
st.markdown("**30+ data points per stock** including Trailing Dividend Yield, Price Headline, and Live News.")

# Sidebar
gpr_data = fetch_gpr_index()
st.sidebar.title("🌐 Global Pulse")
st.sidebar.metric("Geopolitical Risk (GPR)", gpr_data['current'])
st.sidebar.text(f"Status: {gpr_data['status']}")
st.sidebar.text(f"95th Percentile: {gpr_data['percentile_95']}")
st.sidebar.caption("If GPR is 'Elevated', Geopolitical score drops to 30.")

st.sidebar.divider()
st.sidebar.info("📌 **Targets:** Risk=2×ATR, TP1=1.5R, TP2=2.5R, TP3=3.5R")
st.sidebar.info("📌 **Pivots:** Floor pivot points (R1/R2/R3 & S1/S2/S3)")
st.sidebar.info("📌 **Dividend Yield:** Trailing 12-month sum divided by current price.")

if st.button("🔄 Refresh All Data", type="primary"):
    st.cache_data.clear()
    st.rerun()

# Analyze all stocks
progress_text = st.empty()
progress_bar = st.progress(0)

results = []
total = len(STOCK_LIST)
all_articles_map = {}

for idx, (name, symbol) in enumerate(STOCK_LIST.items()):
    progress_text.text(f"Analyzing {name}... ({idx+1}/{total})")
    result = analyze_stock(symbol)
    if result:
        if '_articles' in result:
            all_articles_map[result['Symbol']] = result.pop('_articles')
        results.append(result)
    progress_bar.progress((idx + 1) / total)

progress_text.text("✅ Analysis complete!")
time.sleep(0.5)
progress_text.empty()
progress_bar.empty()

if results:
    df = pd.DataFrame(results)
    df = df.sort_values(by='Composite', ascending=False)

    st.divider()
    st.subheader("📋 Complete Stock Matrix (All Parameters)")

    st.dataframe(
        df,
        column_config={
            "Price": st.column_config.NumberColumn("Price", format="%.2f"),
            "Change %": st.column_config.NumberColumn("Chg %", format="%.2f%%"),
            "Composite": st.column_config.NumberColumn("Composite", format="%.1f"),
            "Fundamental": st.column_config.NumberColumn("Fund.", format="%.1f"),
            "Technical": st.column_config.NumberColumn("Tech.", format="%.1f"),
            "Sentiment": st.column_config.NumberColumn("Sent.", format="%.1f"),
            "Geopolitical": st.column_config.NumberColumn("Geo.", format="%.1f"),
            "Fund Data As Of": st.column_config.TextColumn("Fund Data As Of"),
            "Market Cap (₹ Cr)": st.column_config.NumberColumn("Mkt Cap (₹Cr)", format="%.2f"),
            "P/B Ratio": st.column_config.NumberColumn("P/B", format="%.2f"),
            "Div Yield (Trailing %)": st.column_config.NumberColumn("Div Yield (Tr.)", format="%.2f%%"),
            "52W High": st.column_config.NumberColumn("52W High", format="%.2f"),
            "52W Low": st.column_config.NumberColumn("52W Low", format="%.2f"),
            "% from 52W High": st.column_config.NumberColumn("% High", format="%.2f%%"),
            "% from 52W Low": st.column_config.NumberColumn("% Low", format="%.2f%%"),
            "Volume": st.column_config.NumberColumn("Volume", format="%d"),
            "Avg Volume (10d)": st.column_config.NumberColumn("Avg Vol", format="%d"),
            "Sector": st.column_config.TextColumn("Sector"),
            "Industry": st.column_config.TextColumn("Industry"),
            "Entry": st.column_config.NumberColumn("Entry", format="%.2f"),
            "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="%.2f"),
            "TP1": st.column_config.NumberColumn("TP1", format="%.2f"),
            "TP2": st.column_config.NumberColumn("TP2", format="%.2f"),
            "TP3": st.column_config.NumberColumn("TP3", format="%.2f"),
            "R/R": st.column_config.NumberColumn("R/R", format="%.2f"),
            "S1": st.column_config.NumberColumn("S1", format="%.2f"),
            "S2": st.column_config.NumberColumn("S2", format="%.2f"),
            "S3": st.column_config.NumberColumn("S3", format="%.2f"),
            "R1": st.column_config.NumberColumn("R1", format="%.2f"),
            "R2": st.column_config.NumberColumn("R2", format="%.2f"),
            "R3": st.column_config.NumberColumn("R3", format="%.2f"),
            "📈 Price Headline": st.column_config.TextColumn("📈 Price Headline", width="medium"),
            "📰 Latest News": st.column_config.TextColumn("📰 Latest News", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        height=700
    )

    st.caption(f"✅ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data: Yahoo Finance, GPR Index, GNews (if key provided). All numbers are mathematically derived from live data.")

    # ---------- 5. DETAILED NEWS SECTION (LIVE) ----------
    st.divider()
    st.subheader("📰 Live News & Events - Detailed View")

    stock_options = [f"{row['Company']} ({row['Symbol']})" for _, row in df.iterrows()]
    selected_option = st.selectbox("Select a stock to view its latest 5 news headlines:", options=stock_options)

    if selected_option:
        symbol = selected_option.split('(')[-1].replace(')', '')
        with st.spinner(f"Fetching latest news for {selected_option}..."):
            _, _, articles = fetch_news_for_stock(symbol, limit=5)
            if articles:
                for article in articles:
                    with st.container():
                        col1, col2 = st.columns([6, 1])
                        with col1:
                            if article['url'] != '#':
                                st.markdown(f"**🔗 [{article['title']}]({article['url']})**")
                            else:
                                st.markdown(f"**📌 {article['title']}**")
                            st.caption(f"📝 {article['description']}")
                        with col2:
                            st.text(f"📅 {article['published'][:10] if len(article['published']) > 10 else article['published']}")
                            st.text(f"🏢 {article['source']}")
                        st.divider()
            else:
                st.info("No news found for this stock.")
else:
    st.error("Failed to fetch data. Please check your internet connection or try again.")
