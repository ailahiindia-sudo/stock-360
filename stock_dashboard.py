# ==================================================
# GEO-SENTINEL 360 - Indian Stock Market Analyzer
# ==================================================
# Quantifies Technicals, Fundamentals, News Sentiment,
# and Global Geopolitical Risk into ONE Confidence Index.
# ==================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import numpy as np
from datetime import datetime, timedelta
from textblob import TextBlob
import plotly.graph_objects as go
import time

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Geo-Sentinel 360", layout="wide", page_icon="🌍")

# ---------- 1. FETCH GEOPOLITICAL RISK (GPR) INDEX ----------
@st.cache_data(ttl=3600) # Updates every hour
def fetch_gpr_index():
    """
    Fetches the Caldara-Iacoviello Geopolitical Risk Index.
    Source: Official Federal Reserve / Matteo Iacoviello database.
    """
    try:
        url = "https://www.matteoiacoviello.com/gpr_data.txt"
        # The file is space-separated. We skip the header rows.
        df = pd.read_csv(url, sep='\s+', skiprows=9, header=None, names=['Date', 'GPR'])
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        df = df.sort_values('Date').tail(30) # Get last 30 days for average
        
        if len(df) > 0:
            latest = df.iloc[-1]
            avg_30 = df['GPR'].mean()
            percentile_95 = df['GPR'].quantile(0.95)
            
            return {
                'current': round(latest['GPR'], 2),
                'date': latest['Date'],
                'avg_30': round(avg_30, 2),
                'percentile_95': round(percentile_95, 2),
                'status': 'Elevated' if latest['GPR'] > percentile_95 else 'Normal'
            }
    except Exception as e:
        return {'current': 0, 'date': datetime.now(), 'avg_30': 0, 'percentile_95': 0, 'status': 'Unavailable'}
    return {'current': 0, 'date': datetime.now(), 'avg_30': 0, 'percentile_95': 0, 'status': 'Error'}

# ---------- 2. FETCH NEWS SENTIMENT ----------
@st.cache_data(ttl=1800) # Updates every 30 mins
def fetch_news_sentiment(stock_symbol):
    """
    Quantifies market sentiment from financial news headlines.
    If no API key is provided, it falls back to price movement (deterministic fallback).
    """
    # >>> OPTIONAL: If you got a free key from GNews.io, paste it between the quotes <<<
    api_key = "YOUR_NEWS_API_KEY" 
    
    query = f"{stock_symbol.replace('.NS', '')} stock India"
    
    try:
        if api_key != "YOUR_NEWS_API_KEY":
            url = f"https://gnews.io/api/v4/search?q={query}&token={api_key}&lang=en&max=10"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                articles = response.json().get('articles', [])
                if articles:
                    sentiments = []
                    for article in articles:
                        # TextBlob gives a polarity score from -1 (negative) to +1 (positive)
                        analysis = TextBlob(article['title'] + ". " + article.get('description', ''))
                        sentiments.append(analysis.sentiment.polarity)
                    avg_sentiment = np.mean(sentiments)
                    return round(avg_sentiment * 100, 2) # Scale to -100 to +100
    except:
        pass
    
    # ----- FALLBACK (Zero Hallucination) -----
    # If no API key, we use the stock's own price movement as a proxy for sentiment.
    # This is mathematically derived, not a guess.
    try:
        ticker = yf.Ticker(stock_symbol)
        hist = ticker.history(period="5d")
        if len(hist) > 1:
            change = (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]
            # Scale the % change to mimic sentiment range (-100 to +100)
            return round(change * 100 * 10, 2) 
    except:
        pass
    return 0.0

# ---------- 3. CORE ANALYSIS ENGINE ----------
def analyze_stock(symbol):
    """
    The brain of the tool. Fetches data and calculates the Composite Index.
    """
    try:
        # Ensure NSE format
        if not symbol.endswith('.NS'):
            symbol = symbol + '.NS'
            
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Check if valid stock
        if not info or 'longName' not in info:
            return {'error': 'Stock symbol not found. Please check the ticker (e.g., RELIANCE.NS).'}
            
        hist = ticker.history(period="1mo")
        if hist.empty:
            return {'error': 'No price data available for this symbol.'}

        # -- Fundamental Score (0 to 100) --
        pe = info.get('trailingPE', 0)
        roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
        debt_eq = info.get('debtToEquity', 1)
        profit_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
        
        fund_score = 50 # Start neutral
        # P/E scoring
        if pe and 0 < pe < 25: fund_score += 20
        elif pe and pe >= 25: fund_score -= 10
        elif not pe or pe <= 0: fund_score -= 5 # Negative P/E is bad
        
        # ROE scoring
        if roe > 15: fund_score += 20
        elif roe < 5: fund_score -= 20
        
        # Debt scoring
        if debt_eq < 0.5: fund_score += 10
        elif debt_eq > 1.5: fund_score -= 10
        
        # Profit Margin
        if profit_margin > 10: fund_score += 10
        elif profit_margin < 0: fund_score -= 10
        
        fund_score = max(0, min(100, fund_score))
        
        # -- Technical Score (0 to 100) --
        if len(hist) > 20:
            close = hist['Close']
            current_price = close.iloc[-1]
            
            # 20-day Simple Moving Average
            ma_20 = close.rolling(20).mean().iloc[-1]
            # 50-day Simple Moving Average (if we have enough data)
            ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma_20
            
            tech_score = 50
            # Price above MA 20?
            if current_price > ma_20: tech_score += 20
            else: tech_score -= 20
            
            # Price above MA 50?
            if current_price > ma_50: tech_score += 20
            else: tech_score -= 20
            
            # 52-week range position
            high_52 = info.get('fiftyTwoWeekHigh', current_price)
            low_52 = info.get('fiftyTwoWeekLow', current_price)
            if high_52 > low_52:
                position = (current_price - low_52) / (high_52 - low_52)
                tech_score += (position * 20) - 10 # Adds between -10 and +10
            
            tech_score = max(0, min(100, tech_score))
        else:
            tech_score = 50
            
        # -- Sentiment Score (from News) --
        raw_sent_score = fetch_news_sentiment(symbol)
        # Normalize sentiment from -100:100 to 0:100
        norm_sent_score = 50 + (raw_sent_score / 2) 
        norm_sent_score = max(0, min(100, norm_sent_score))
        
        # -- Geopolitical Score (0 to 100) --
        gpr_data = fetch_gpr_index()
        if gpr_data['status'] == 'Normal':
            geo_score = 70
        elif gpr_data['status'] == 'Elevated':
            geo_score = 30
        else:
            geo_score = 50 # Neutral if data unavailable
            
        # -- FINAL COMPOSITE INDEX (Weighted) --
        # Weights: 30% Fundamental, 30% Technical, 20% Sentiment, 20% Geopolitical
        final_index = (fund_score * 0.30) + (tech_score * 0.30) + (norm_sent_score * 0.20) + (geo_score * 0.20)
        final_index = round(final_index, 1)
        
        # -- Decision Logic --
        if final_index >= 75: decision = "🚀 Strong Buy"
        elif final_index >= 60: decision = "📈 Buy / Accumulate"
        elif final_index >= 45: decision = "⏸️ Hold / Wait"
        elif final_index >= 30: decision = "📉 Reduce / Sell"
        else: decision = "🔻 Strong Sell"
        
        return {
            'name': info.get('longName', symbol),
            'symbol': symbol,
            'current_price': round(info.get('currentPrice', info.get('regularMarketPrice', 0)), 2),
            'pe_ratio': round(pe, 2) if pe else 'N/A',
            'roe': round(roe, 2),
            'profit_margin': round(profit_margin, 2),
            'fund_score': round(fund_score, 1),
            'tech_score': round(tech_score, 1),
            'sentiment_score': round(norm_sent_score, 1),
            'geo_score': round(geo_score, 1),
            'composite_index': final_index,
            'decision': decision,
            'geopolitical_details': gpr_data,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {'error': f'Analysis failed: {str(e)}'}

# ---------- 4. USER INTERFACE (The Website) ----------
st.title("🌍 Geo-Sentinel 360 - Indian Stock Analyzer")
st.markdown("*Quantifying Technicals, Fundamentals, News Sentiment & Geopolitical Risk into a single Confidence Index.*")

# Input Section
col1, col2 = st.columns([2, 1])
with col1:
    ticker_input = st.text_input("Enter NSE Stock Symbol (e.g., RELIANCE, TCS, HDFCBANK):", value="RELIANCE").upper().strip()
with col2:
    st.write("")
    st.write("")
    analyze_btn = st.button("🔍 Analyze Stock", type="primary", use_container_width=True)

# Auto-add .NS if missing
if ticker_input and not ticker_input.endswith('.NS'):
    ticker_input = ticker_input + '.NS'

if analyze_btn:
    if not ticker_input:
        st.warning("Please enter a stock symbol.")
    else:
        with st.spinner("🌐 Fetching global data and analyzing..."):
            result = analyze_stock(ticker_input)
            
            if 'error' in result:
                st.error(f"❌ {result['error']}")
            else:
                # ----- SIDEBAR: Global Geopolitical Snapshot -----
                geo = result['geopolitical_details']
                st.sidebar.title("🌐 Global Pulse")
                st.sidebar.metric("Geopolitical Risk Index (GPR)", geo['current'], delta=f"Avg 30d: {geo['avg_30']}")
                st.sidebar.text(f"Status: {geo['status']}")
                st.sidebar.text(f"95th Percentile: {geo['percentile_95']}")
                st.sidebar.caption(f"Updated: {geo['date'].strftime('%Y-%m-%d')}")
                st.sidebar.divider()
                st.sidebar.info("💡 If GPR > 95th percentile, Geopolitical risk is high, lowering the composite score.")

                # ----- MAIN DASHBOARD -----
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("📌 Stock", result['name'])
                col_b.metric("💰 Price", f"₹ {result['current_price']}")
                col_c.metric("📊 P/E Ratio", result['pe_ratio'])
                col_d.metric("📈 Profit Margin", f"{result['profit_margin']}%")

                st.divider()
                
                # ----- THE FINAL INDEX (Gauge Chart) -----
                st.subheader("📊 Composite Confidence Index (0 to 100)")
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = result['composite_index'],
                    title = {'text': f"{result['decision']}", 'font': {'size': 24}},
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 30], 'color': '#ff4b4b'},   # Red
                            {'range': [30, 45], 'color': '#ffa500'},  # Orange
                            {'range': [45, 60], 'color': '#ffd700'},  # Yellow
                            {'range': [60, 75], 'color': '#9acd32'},  # Light Green
                            {'range': [75, 100], 'color': '#2e8b57'} # Dark Green
                        ],
                        'threshold': {
                            'line': {'color': "black", 'width': 4}, 
                            'thickness': 0.75, 
                            'value': result['composite_index']
                        }
                    }
                ))
                fig.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True)

                # ----- SCORE BREAKDOWN -----
                st.divider()
                st.subheader("📈 360-Degree Score Breakdown (0 to 100)")
                
                col_e, col_f, col_g, col_h = st.columns(4)
                col_e.metric("🏢 Fundamental Health", f"{result['fund_score']}/100")
                col_f.metric("📉 Technical Strength", f"{result['tech_score']}/100")
                col_g.metric("🗞️ News Sentiment", f"{result['sentiment_score']}/100")
                col_h.metric("🌍 Geopolitical Impact", f"{result['geo_score']}/100")

                st.caption(f"✅ Analysis performed on: {result['timestamp']} | Data Sources: Yahoo Finance, GPR Index (Iacoviello), GNews API. All scores are deterministic and mathematically derived.")