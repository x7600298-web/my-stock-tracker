import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# --- 1. 網頁基礎設定 ---
st.set_page_config(page_title="AI 投資戰情室", layout="wide")

# 注入自定義 CSS：黑魂專業風格
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    div[data-testid="stMetric"] {
        background-color: #1E2129;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #30363D;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 雲端串接與防呆處理 ---
# 請在此貼上你的 Google Sheets 網址
RAW_URL = "https://docs.google.com/spreadsheets/d/1modHzl33LKOCGoRrobrMCaNEO5Phebe3Vl8eIUScU9M/edit?gid=0#gid=0"

if "docs.google.com" in RAW_URL:
    GOOGLE_SHEET_URL = RAW_URL.split("/edit")[0] + "/export?format=csv"
else:
    GOOGLE_SHEET_URL = RAW_URL

@st.cache_data(ttl=60)
def load_gsheets(url):
    try:
        df = pd.read_csv(url)
        # 強制移除標題空格，避免 KeyError: 'Ticker'
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        return None

# --- 3. 側邊欄：數據源管理 ---
with st.sidebar:
    st.header("📊 數據來源")
    inventory_df = load_gsheets(GOOGLE_SHEET_URL)
    
    if inventory_df is not None and 'Ticker' in inventory_df.columns:
        st.success("✅ 雲端資料同步中")
        # 取得不重複的代號清單
        ticker_list = inventory_df['Ticker'].dropna().unique().tolist()
        selected_ticker = st.selectbox("選擇我的持股", ticker_list)
        
        # 抓取該標的在 Sheets 裡的資訊
        user_row = inventory_df[inventory_df['Ticker'] == selected_ticker].iloc[0]
        stock_id = str(selected_ticker).upper()
        my_cost = float(user_row['Buy_Price'])
        my_shares = int(user_row['Shares'])
        
        # 讀取 analyzer.py 寫回來的 AI 建議 (如果有的話)
        ai_advice_from_sheet = user_row.get('AI Advice', None)
        growth_from_sheet = user_row.get('Growth', None)
    else:
        st.error("❌ 找不到 'Ticker' 欄位，請檢查表格標題")
        stock_id = st.text_input("手動輸入代號", value="VT").upper()
        my_cost = st.number_input("平均成本", value=0.0)
        my_shares = st.number_input("持有股數", value=0)
        ai_advice_from_sheet = None

# --- 4. 數據抓取與分析引擎 ---
def get_analysis(ticker):
    # 自動補全台股格式
    yf_ticker = f"{ticker}.TW" if ticker.isdigit() else ticker
    df = yf.download(yf_ticker, period="1y", auto_adjust=True)
    if df.empty: return None
    
    # 處理 yfinance 多重索引
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(yf_ticker, axis=1, level=1)
        
    # 計算技術指標
    df['MA20'] = df['Close'].rolling(20).mean()
    df['STD'] = df['Close'].rolling(20).std()
    df['Upper'] = df['MA20'] + (df['STD'] * 2)
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    
    # RSI 計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    return df

df = get_analysis(stock_id)

# --- 5. 主畫面呈現 ---
if df is not None:
    current_price = float(df['Close'].iloc[-1])
    rsi_val = float(df['RSI'].iloc[-1])
    upper_val = float(df['Upper'].iloc[-1])
    lower_val = float(df['Lower'].iloc[-1])

    st.title(f"🔍 {stock_id} 分析師診斷報告")
    
    tab1, tab2 = st.tabs(["📈 即時戰情", "💰 資產概況"])

    with tab1:
        # AI 決策看板
        st.subheader("🤖 AI 投資決策建議")
        c1, c2, c3 = st.columns(3)
        
        # 決策邏輯：優先使用 analyzer.py 的結果，若無則現場計算
        if ai_advice_from_sheet and str(ai_advice_from_sheet) != 'nan':
            current_advice = ai_advice_from_sheet
        else:
            if current_price <= lower_val: current_advice = "💎 建議買進"
            elif current_price >= upper_val: current_advice = "💰 建議變現"
            else: current_advice = "⚖️ 持續觀望"

        c1.metric("診斷結果", current_advice)
        c2.metric("RSI 強弱", f"{rsi_val:.1f}")
        c3.metric("目前市價", f"${current_price:,.2f}")

        # K 線圖
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"))
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='rgba(255,0,0,0.3)'), name="預估高點"))
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='rgba(0,255,0,0.3)'), name="預估低點"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("持有資產明細")
        if my_cost > 0:
            total_cost = my_cost * my_shares
            current_value = current_price * my_shares
            profit = current_value - total_cost
            roi = (profit / total_cost) * 100
            
            m1, m2, m3 = st.columns(3)
            m1.metric("資產現值", f"${current_value:,.2f}")
            m2.metric("預估損益", f"${profit:,.2f}", f"{roi:.2f}%")
            m3.metric("持有股數", f"{my_shares} 股")
            
            if growth_from_sheet:
                st.info(f"雲端紀錄成長率：{growth_from_sheet}")
        else:
            st.warning("請確保 Google Sheets 中已填寫 Buy_Price 與 Shares")

else:
    st.error("無法取得股票數據，請確認代號是否正確（台股請輸入數字，美股輸入代號）。")
