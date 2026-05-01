import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 網頁基礎設定
st.set_page_config(page_title="個人股票戰情室", layout="wide")

# --- 雲端串接設定區 ---
# 請將下方的網址替換成你的 Google Sheets 共用網址
# 記得要把網址最後面的 /edit... 之後的文字改成 /export?format=csv
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1modHzl33LKOCGoRrobrMCaNEO5Phebe3Vl8eIUScU9M/export?format=csv"

@st.cache_data(ttl=600)  # 每 10 分鐘更新一次雲端資料
def load_data_from_gsheets(url):
    try:
        df = pd.read_csv(url)
        return df
    except:
        return None

# --- 側邊欄邏輯 ---
with st.sidebar:
    st.header("📊 數據來源")
    inventory_df = load_data_from_gsheets(GOOGLE_SHEET_URL)
    
    if inventory_df is not None:
        st.success("✅ 雲端資料同步中")
        # 讓使用者從清單選擇代號
        target_list = inventory_df['Ticker'].tolist()
        selected_ticker = st.selectbox("選擇追蹤標的", target_list)
        
        # 自動抓取對應的成本與股數
        user_row = inventory_df[inventory_df['Ticker'] == selected_ticker].iloc[0]
        stock_id = selected_ticker.upper()
        my_cost = float(user_row['Buy_Price'])
        my_shares = int(user_row['Shares'])
    else:
        st.warning("⚠️ 模式：手動輸入 (未偵測到雲端表)")
        stock_id = st.text_input("輸入股票代號", value="VT").upper()
        my_cost = st.number_input("平均買入成本", value=0.0)
        my_shares = st.number_input("持有股數", value=0)

# --- 抓取股市即時數據 ---
@st.cache_data(ttl=3600)
def get_stock_price(ticker):
    try:
        # 下載最近一年數據，自動調整格式
        data = yf.download(ticker, period="1y", auto_adjust=True)
        return data
    except:
        return None

df = get_stock_price(stock_id)

if df is not None and not df.empty:
    # 針對 yfinance 格式去殼
    if isinstance(df.columns, pd.MultiIndex):
        close_series = df['Close'][stock_id]
        open_series = df['Open'][stock_id]
        high_series = df['High'][stock_id]
        low_series = df['Low'][stock_id]
    else:
        close_series = df['Close']
        open_series = df['Open']
        high_series = df['High']
        low_series = df['Low']

    current_price = float(close_series.iloc[-1])
    
    # 計算動盪指標 (布林通道)
    ma20 = close_series.rolling(20).mean()
    std20 = close_series.rolling(20).std()
    upper = ma20 + (std20 * 2)
    lower = ma20 - (std20 * 2)

    # --- 畫面呈現：損益看板 ---
    st.title(f"📈 {stock_id} 實質損益與動盪分析")
    
    c1, c2, c3 = st.columns(3)
    if my_cost > 0:
        total_cost = my_cost * my_shares
        market_value = current_price * my_shares
        profit = market_value - total_cost
        roi = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        c1.metric("資產現值", f"${market_value:,.2f}")
        c2.metric("預估損益", f"${profit:,.2f}", f"{roi:.2f}%")
        c3.metric("目前市價", f"${current_price:,.2f}")
    else:
        st.info("請在左側輸入或於 Google Sheets 設定成本資訊。")

    # --- 畫面呈現：動盪分析 ---
    st.write("---")
    curr_upper = float(upper.iloc[-1])
    curr_lower = float(lower.iloc[-1])

    if current_price >= curr_upper:
        st.error(f"🚨 高動盪警戒：股價觸及壓力線 (${curr_upper:.2f})，考慮分批出售。")
    elif current_price <= curr_lower:
        st.success(f"💎 合理位機會：股價回落支撐線 (${curr_lower:.2f})，可考慮分批佈局。")
    else:
        st.info(f"📊 盤整期：股價在合理波動區間，距離壓力位尚有 {((curr_upper-current_price)/current_price)*100:.2f}%。")

    # --- 畫面呈現：圖表 ---
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=open_series, high=high_series, low=low_series, close=close_series, name="K線"))
    fig.add_trace(go.Scatter(x=df.index, y=upper, line=dict(color='rgba(255,0,0,0.3)'), name="動盪上軌"))
    fig.add_trace(go.Scatter(x=df.index, y=lower, line=dict(color='rgba(0,255,0,0.3)'), name="動盪下軌"))
    
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("無法讀取股票數據，請確認代號是否正確。")
