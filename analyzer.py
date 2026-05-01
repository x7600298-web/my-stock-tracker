import gspread
from google.oauth2.service_account import Credentials
import yfinance as yf
import pandas as pd
import time

# --- 1. 連線設定 ---
# 這裡定義要存取的權限範圍
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

try:
    # 讀取你的 Google Cloud JSON 憑證
    creds = Credentials.from_service_account_file('your-key.json', scopes=scope)
    client = gspread.authorize(creds)
    
    # 打開試算表 (請填入你精確的試算表名稱)
    # 注意：必須先在 Google Sheets 將編輯權限共用給 JSON 裡的 client_email
    sheet_obj = client.open("你的股票表格名稱") 
    sheet = sheet_obj.worksheet("Stocks")
    
    print("✅ 成功連線至 Google Sheets")
except Exception as e:
    print(f"❌ 連線失敗: {e}")
    exit()

# --- 2. 抓取資料庫內容 ---
records = sheet.get_all_records()
if not records:
    print("查無資料，請確認 Stocks 分頁是否有數據。")
    exit()

df_inventory = pd.DataFrame(records)
updates = []

print(f"探測到 {len(df_inventory)} 筆標的，開始分析...")

# --- 3. 分析師評估邏輯 ---
for index, row in df_inventory.iterrows():
    ticker = str(row['Ticker']).strip()
    
    # 自動識別代號：純數字視為台股 (如 2330 -> 2330.TW)，其餘視為美股
    yf_ticker = f"{ticker}.TW" if ticker.isdigit() else ticker
    
    print(f"正在分析: {yf_ticker}...")
    
    try:
        # 下載最近一年的數據
        data = yf.download(yf_ticker, period="1y", auto_adjust=True)
        
        if data.empty:
            updates.append(["N/A", "N/A", "無法取得數據"])
            continue
            
        # 計算技術指標
        close = float(data['Close'].iloc[-1])
        ma20 = data['Close'].rolling(20).mean().iloc[-1]
        std20 = data['Close'].rolling(20).std().iloc[-1]
        
        # 布林通道上下軌
        upper = ma20 + (std20 * 2)
        lower = ma20 - (std20 * 2)
        
        # 成長率 (相較於你的 Buy_Price)
        buy_price = float(row['Buy_Price'])
        growth = ((close - buy_price) / buy_price) * 100 if buy_price > 0 else 0
        
        # AI 決策邏輯
        if close <= lower:
            advice = "💎 建議買進"
        elif close >= upper:
            advice = "💰 建議變現"
        else:
            advice = "⚖️ 持續觀望"
            
        updates.append([round(close, 2), f"{growth:.2f}%", advice])
        
        # 避免請求過快被 Yahoo 封鎖
        time.sleep(1)
        
    except Exception as e:
        print(f"分析 {ticker} 時出錯: {e}")
        updates.append(["Error", "Error", "分析出錯"])

# --- 4. 寫回 Sheets (更新 E, F, G 欄) ---
# 起點是 E2 (現價), F2 (成長率), G2 (AI 建議)
try:
    end_row = len(updates) + 1
    sheet.update(f'E2:G{end_row}', updates)
    print(f"🚀 AI 分析完成！已更新 {len(updates)} 筆建議至雲端。")
except Exception as e:
    print(f"❌ 寫回資料時出錯: {e}")