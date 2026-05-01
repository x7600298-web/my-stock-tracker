import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# 網頁設定
st.set_page_config(page_title="AI 股票分析師系統", layout="wide")

# --- 雲端串接設定區 ---
# 請在此處貼上你的 Google Sheets 共用網址
RAW_URL = "https://docs.google.com/spreadsheets/d/1modHzl33LKOCGoRrobrMCaNEO5Phebe3Vl8eIUScU9M/edit?gid=0#gid=0"

# 自動處理網址轉換邏輯
if "docs.google.com" in RAW_URL:
    base_url = RAW_URL.split("/edit")[0]
    GOOGLE_SHEET_URL = f"{base_url}/export?format=csv"
else:
    GOOGLE_SHEET_URL = RAW_URL

@st.cache_data(ttl=60)
def load_gsheets(url):
    try:
        df = pd.read_csv(url)
        # 移除欄位名稱可能的空格
        df.columns = df.columns.str.strip()
        return df
    except:
        return None

# --- 技術指標計算 ---
def add_indicators(df):
    # 布林通道 (20日標準差)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD'] = df['Close'].rolling(window=20).std()
    df['Upper'] = df['MA20'] + (df['STD'] * 2)
    df['Lower'] = df['MA20'] - (df['STD'] * 2)
    
    # RSI 指標 (14日)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

# --- 介面邏輯 ---
with st.sidebar:
    st.header("📊 數據來源")
    inventory_df = load_gsheets(GOOGLE_SHEET_URL)
    
    if inventory_df is not None and not inventory_df.empty:
        st.success("✅ 雲端連線成功")
        selected_ticker = st.selectbox("我的庫存清單", inventory_df['Ticker'].unique())
        user_row = inventory_df[inventory_df['Ticker'] == selected_ticker].iloc[0]
        stock_id = selected_ticker.upper()
        my_cost = float(user_row['Buy_Price'])
        my_shares = int(user_row['Shares'])
    else:
        st.warning("⚠️ 模式：手動輸入 (未偵測到雲端表)")
        stock_id = st.text_input("輸入股票代號", value="VT").upper()
        my_cost = st.number_input("平均買入成本", value=0.0)
        my_shares = st.number_input("持有股數", value=0)

# 抓取數據
@st.cache_data(ttl=3600)
def get_data(ticker):
    try:
        df = yf.download(ticker, period="1y", auto_adjust=True)
        return df
    except:
        return None

df = get_data(stock_id)

if df is not None and not df.empty:
    # 格式處理
    if isinstance(df.columns, pd.MultiIndex):
        df_flat = pd.DataFrame(index=df.index)
        df_flat['Close'] = df['Close'][stock_id]
        df_flat['Open'] = df['Open'][stock_id]
        df_flat['High'] = df['High'][stock_id]
        df_flat['Low'] = df['Low'][stock_id]
        df = df_flat
    
    df = add_indicators(df)
    current_price = float(df['Close'].iloc[-1])
    rsi_val = float(df['RSI'].iloc[-1])
    upper_val = float(df['Upper'].iloc[-1])
    lower_val = float(df['Lower'].iloc[-1])

    # --- 畫面：標題與個人損益 ---
    st.title(f"🔍 {stock_id} 分析師診斷報告")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    if my_cost > 0:
        profit = (current_price - my_cost) * my_shares
        roi = (profit / (my_cost * my_shares)) * 100
        col_p1.metric("資產價值", f"${current_price * my_shares:,.2f}")
        col_p2.metric("預估獲利", f"${profit:,.2f}", f"{roi:.2f}%")
        col_p3.metric("RSI 強弱值", f"{rsi_val:.1f}")

    # --- 畫面：分析師預測區 ---
    st.write("---")
    st.subheader("🤖 AI 買賣點預測")
    
    c1, c2 = st.columns(2)
    with c1:
        st.write("📉 **低點分佈 (支撐位)**")
        st.title(f"${lower_val:.2f}")
        st.caption("統計學上的相對安全買入區間")
        
    with c2:
        st.write("📈 **高點分佈 (壓力位)**")
        st.title(f"${upper_val:.2f}")
        st.caption("統計學上的潛在獲利回檔區間")

    # 智慧診斷
    if current_price <= lower_val and rsi_val < 35:
        st.success("🌟 **診斷結果：強烈買入訊號**。股價進入超跌區且觸及地板，適合佈局。")
    elif current_price >= upper_val and rsi_val > 65:
        st.error("🔥 **診斷結果：超買警訊**。股價衝出天花板且情緒過熱，建議分批減碼。")
    elif rsi_val < 40:
        st.warning("⚖️ **診斷結果：股價偏弱**。目前市場信心不足，建議等站穩支撐位再行動。")
    else:
        st.info("⚖️ **診斷結果：區間震盪**。股價處於合理動盪範圍，暫時無極端訊號。")

    # --- 畫面：視覺化 K 線 ---
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"))
    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='rgba(255,0,0,0.3)'), name="預估高點"))
    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='rgba(0,255,0,0.3)'), name="預估低點"))
    
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("數據載入失敗，請檢查代號。")
