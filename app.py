import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# 網頁設定：將佈局設為寬屏，方便在電腦與手機觀看
st.set_page_config(page_title="個人股票戰情室", layout="wide")

st.title("📈 股票動盪與實質損益分析")

# --- 1. 側邊欄設定區 ---
with st.sidebar:
    st.header("📌 設定標的")
    # 支援全球代號，如 VT, MSFT, 2330.TW, 006208.TW
    stock_id = st.text_input("輸入股票代號", value="VT").upper()
    
    st.header("💰 我的庫存 (實質分析)")
    my_cost = st.number_input("平均買入成本", value=0.0, step=0.01)
    my_shares = st.number_input("持有股數", value=0, step=1)
    
    st.write("---")
    st.caption("註：台股請記得加 .TW (例如 2330.TW)")

# --- 2. 數據抓取與處理 (解決 MultiIndex 格式問題) ---
@st.cache_data(ttl=3600)  # 快取資料一小時，避免頻繁抓取被封鎖
def get_stock_data(ticker):
    try:
        # 下載最近一年的數據，auto_adjust=True 讓格式變簡單
        df = yf.download(ticker, period="1y", auto_adjust=True)
        return df
    except Exception as e:
        return None

df = get_stock_data(stock_id)

if df is not None and not df.empty:
    # 針對 yfinance 新版格式進行「去殼」處理，確保拿到正確的 Close 數值
    if isinstance(df.columns, pd.MultiIndex):
        # 如果是多重索引，取出該標的的收盤價
        close_series = df['Close'][stock_id]
        open_series = df['Open'][stock_id]
        high_series = df['High'][stock_id]
        low_series = df['Low'][stock_id]
    else:
        close_series = df['Close']
        open_series = df['Open']
        high_series = df['High']
        low_series = df['Low']

    # 確保數值是單一浮點數
    current_price = float(close_series.iloc[-1])
    
    # --- 3. 計算技術指標 (分析動盪) ---
    ma20 = close_series.rolling(window=20).mean()
    std20 = close_series.rolling(window=20).std()
    upper_band = ma20 + (std20 * 2)  # 高估區 (動盪上軌)
    lower_band = ma20 - (std20 * 2)  # 低估區 (動盪下軌)

    # --- 4. 實質損益看板 ---
    st.subheader("📋 投資表現摘要")
    c1, c2, c3 = st.columns(3)
    
    if my_cost > 0:
        total_cost = my_cost * my_shares
        market_value = current_price * my_shares
        profit = market_value - total_cost
        roi = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        c1.metric("目前總價值", f"${market_value:,.2f}")
        # 損益顯示顏色：正數為紅/綠(視市場慣例)，這裡預設紅漲綠跌
        c2.metric("預估總損益", f"${profit:,.2f}", f"{roi:.2f}%")
        c3.metric("當前市價", f"${current_price:,.2f}")
    else:
        st.info("💡 請在左側輸入「買入成本」與「股數」來啟用實質損益追蹤。")

    # --- 5. 動盪分析與出售建議 ---
    st.write("---")
    st.subheader("🔍 股價合理位分析")
    
    curr_upper = float(upper_band.iloc[-1])
    curr_lower = float(lower_band.iloc[-1])
    
    if current_price >= curr_upper:
        st.warning(f"⚠️ **目前狀態：股價過熱**｜股價已觸及動盪上軌 (${curr_upper:.2f})，建議檢查是否分批獲利了結。")
    elif current_price <= curr_lower:
        st.success(f"✅ **目前狀態：股價低估**｜股價跌破動盪下軌 (${curr_lower:.2f})，若基本面良好，此處為合理加碼位。")
    else:
        dist_pct = ((curr_upper - current_price) / current_price) * 100
        st.info(f"⚖️ **目前狀態：區間震盪**｜股價處於合理動盪區間。距離上方壓力位還有約 {dist_pct:.2f}% 的空間。")

    # --- 6. 互動式圖表 ---
    fig = go.Figure()
    
    # 繪製 K 線
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=open_series,
        high=high_series,
        low=low_series,
        close=close_series,
        name="股價走勢"
    ))
    
    # 繪製布林通道 (分析動盪合理位)
    fig.add_trace(go.Scatter(x=df.index, y=upper_band, line=dict(color='rgba(255, 99, 71, 0.5)'), name="壓力線 (高)"))
    fig.add_trace(go.Scatter(x=df.index, y=lower_band, line=dict(color='rgba(144, 238, 144, 0.5)'), name="支撐線 (低)"))
    
    # 設定圖表樣式
    fig.update_layout(
        height=600,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("無法取得數據，請確認股票代號是否正確。")