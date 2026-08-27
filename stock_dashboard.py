# ==================================================
# GEO-SENTINEL 360 - Watchlist Dashboard (Table View)
# ==================================================
# Displays ALL stocks in a sortable table with their
# quantified Sentiment, Geopolitical, and Composite scores.
# ==================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import numpy as np
from datetime import datetime
from textblob import TextBlob
import time

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Geo-Sentinel 360 - Watchlist", layout="wide", page_icon="📊")

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
    """Fetches the global Geopolitical Risk Index."""
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

# ---------- 2. FETCH NEWS SENTIMENT (with fallback) ----------
@st.cache_data(ttl=1800)
def fetch_news_sentiment(stock_symbol):
    """Quantifies sentiment from news headlines or uses price fallback."""
    # Optional: Paste your GNews API key here for real news analysis
    api_key = "YOUR_NEWS_API_KEY" 
    query = stock_symbol.replace('.NS', '') + " stock India"
    
    try:
        if api_key != "YOUR_NEWS_API_KEY":
            url = f"https://gnews.io/api/v4/search?q={query}&token={api_key}&lang=en&max=10"
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                articles = response.json().get('articles', [])
                if articles:
                    sentiments = []
                    for article in articles:
                        analysis = TextBlob(article['title'] + ". " + article.get('description', ''))
                        sentiments.append(analysis.sentiment.polarity)
                    avg_sentiment = np.mean(sentiments)
                    return round(avg_sentiment * 100, 2)
    except:
        pass
    
    # Deterministic fallback (based on price movement - zero hallucination)
    try:
        ticker = yf.Ticker(stock_symbol)
        hist = ticker.history(period="5d")
        if len(hist) > 1:
            change = (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]
            return round(change * 100 * 10, 2)
    except:
        pass
    return 0.0

# ---------- 3. ANALYZE A SINGLE STOCK ----------
def analyze_stock(symbol):
    """Runs the 360-degree analysis for a single stock ticker."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or 'longName' not in info:
            return None
            
        hist = ticker.history(period="1mo")
        if hist.empty:
            return None

        # -- Fundamental Score --
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
        
        # -- Technical Score --
        if len(hist) > 20:
            close = hist['Close']
            current_price = close.iloc[-1]
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
        else:
            tech_score = 50
            
        # -- Sentiment Score --
        raw_sent = fetch_news_sentiment(symbol)
        norm_sent_score = 50 + (raw_sent / 2)
        norm_sent_score = max(0, min(100, norm_sent_score))
        
        # -- Geopolitical Score (Global, same for all stocks) --
        gpr = fetch_gpr_index()
        geo_score = 70 if gpr['status'] == 'Normal' else (30 if gpr['status'] == 'Elevated' else 50)
            
        # -- FINAL COMPOSITE INDEX --
        final_index = (fund_score * 0.30) + (tech_score * 0.30) + (norm_sent_score * 0.20) + (geo_score * 0.20)
        final_index = round(final_index, 1)
        
        # -- Decision --
        if final_index >= 75: decision = "Strong Buy"
        elif final_index >= 60: decision = "Buy"
        elif final_index >= 45: decision = "Hold"
        elif final_index >= 30: decision = "Reduce"
        else: decision = "Sell"
        
        return {
            'Company': info.get('longName', symbol),
            'Symbol': symbol.replace('.NS', ''),
            'Price (₹)': round(info.get('currentPrice', info.get('regularMarketPrice', 0)), 2),
            'Fundamental': round(fund_score, 1),
            'Technical': round(tech_score, 1),
            'Sentiment': round(norm_sent_score, 1),
            'Geopolitical': round(geo_score, 1),
            'Composite Index': final_index,
            'Signal': decision
        }
    except:
        return None

# ---------- 4. MAIN DASHBOARD UI ----------
st.title("📊 Geo-Sentinel 360 - Watchlist Dashboard")
st.markdown("**All Nifty 50 stocks analyzed in real-time.** Click any column header to sort. The **Composite Index** combines all 4 factors.")

# Display Global Geopolitical Pulse in the sidebar
gpr_data = fetch_gpr_index()
st.sidebar.title("🌐 Global Pulse")
st.sidebar.metric("Geopolitical Risk (GPR)", gpr_data['current'])
st.sidebar.text(f"Status: {gpr_data['status']}")
st.sidebar.text(f"95th Percentile: {gpr_data['percentile_95']}")
st.sidebar.caption("If GPR is 'Elevated', Geopolitical scores drop to 30/100.")
st.sidebar.divider()
st.sidebar.info("💡 Click the 'Refresh Data' button below to fetch the latest prices and news sentiment.")

# Refresh Button
if st.button("🔄 Refresh All Data", type="primary", use_container_width=False):
    st.cache_data.clear()
    st.rerun()

# Progress bar for analysis
progress_text = st.empty()
progress_bar = st.progress(0)

# Analyze all stocks
results = []
total = len(STOCK_LIST)
counter = 0

for name, symbol in STOCK_LIST.items():
    progress_text.text(f"Analyzing {name}... ({counter+1}/{total})")
    result = analyze_stock(symbol)
    if result:
        results.append(result)
    counter += 1
    progress_bar.progress(counter / total)

progress_text.text("Analysis complete! Displaying results.")
time.sleep(0.5)
progress_text.empty()
progress_bar.empty()

# Convert to DataFrame
if results:
    df = pd.DataFrame(results)
    
    # Sort by Composite Index (Highest first) by default
    df = df.sort_values(by='Composite Index', ascending=False)
    
    # Display the interactive table
    st.divider()
    st.subheader("📋 Stock Performance Matrix")
    
    # Use st.dataframe for native sorting (just click the column header!)
    # Apply color formatting to the Composite Index for easy scanning
    st.dataframe(
        df,
        column_config={
            "Composite Index": st.column_config.NumberColumn(
                "Composite Index",
                help="Overall score out of 100. Higher is better.",
                format="%.1f",
                width="small",
            ),
            "Fundamental": st.column_config.NumberColumn(
                "Fundamental",
                help="Financial health score.",
                format="%.1f",
                width="small",
            ),
            "Technical": st.column_config.NumberColumn(
                "Technical",
                help="Price trend and momentum score.",
                format="%.1f",
                width="small",
            ),
            "Sentiment": st.column_config.NumberColumn(
                "Sentiment",
                help="News and market mood score.",
                format="%.1f",
                width="small",
            ),
            "Geopolitical": st.column_config.NumberColumn(
                "Geopolitical",
                help="Global risk impact score.",
                format="%.1f",
                width="small",
            ),
            "Price (₹)": st.column_config.NumberColumn(
                "Price (₹)",
                format="%.2f",
                width="small",
            ),
            "Signal": st.column_config.TextColumn(
                "Signal",
                help="Action recommendation based on Composite Index.",
                width="medium",
            )
        },
        hide_index=True,
        use_container_width=True,
        height=600
    )
    
    # Show timestamp
    st.caption(f"✅ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data: Yahoo Finance & GPR Index (Iacoviello)")

else:
    st.error("Failed to fetch data. Please check your internet connection or try again later.")
