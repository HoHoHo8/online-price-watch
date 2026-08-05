import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# 確保 data 資料夾存在
os.makedirs('data', exist_ok=True)

# 香港時間設定 (UTC+8)
hkt_timezone = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt_timezone)
today_str = now_hkt.strftime('%Y-%m-%d')
month_str = now_hkt.strftime('%Y_%m')
monthly_file_path = f'data/prices_{month_str}.csv'

print(f"📅 當前香港日期: {today_str}")

# 1. 萬能欄位別名對照表 (Alias Map) - 包含所有可能出現的 Header
HEADER_ALIASES = {
    'cat1': ['cat1', '貨品分類1', '貨品分類 1', 'cat1_name', 'category1', 'main_category'],
    'category': ['category', 'cat2', '貨品分類2', '貨品分類 2', 'cat2_name', 'sub_category', '貨品分類3'],
    'item_id': ['item_id', '貨品編號', 'code', 'id', 'item_code'],
    'brand': ['brand', '品牌', 'brand_name', 'brand_zh'],
    'item_name': ['item_name', '貨品名稱', 'name', 'title', 'name_zh'],
    'supermarket': ['supermarket', '超市代碼', '超市名稱', 'shop', 'shop_name', 'store'],
    'price': ['price', '價格', '價錢', 'retail_price']
}

# 2. 超市名稱映射表
SHOP_MAP = {
    'WELLCOME': '惠康',
    'PARKNSHOP': '百佳',
    'JASONS': 'Market Place / Jasons',
    'MARKETPLACE': 'Market Place',
    'AEON': 'AEON',
    'TASTE': 'TASTE',
    'FUSION': 'FUSION',
    'DONKI': 'DON DON DONKI',
    'MANNINGS': '萬寧',
    'WATSONS': '屈臣氏',
    'HKTVMALL': 'HKTVmall'
}

def standardize_dataframe(df_input, default_date=today_str):
    """將任意格式/Header 的 DataFrame 統一轉換為標準格式"""
    df = df_input.copy()
    
    # 欄位標頭去空白
    df.columns = [str(c).strip() for c in df.columns]
    
    # 建立映射表
    rename_dict = {}
    for standard_col, aliases in HEADER_ALIASES.items():
        for col in df.columns:
            if col.lower() in [a.lower() for a in aliases] or any(a in col for a in aliases):
                rename_dict[col] = standard_col
                break

    df.rename(columns=rename_dict, inplace=True)
    
    # 檢查並補充 Missing 欄位
    if 'date' not in df.columns:
        df['date'] = default_date
    else:
        # 統一日期格式 (例如將 3/8/2026 轉為 2026-08-03)
        df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True).dt.strftime('%Y-%m-%d')
        df['date'] = df['date'].fillna(default_date)

    for col in ['cat1', 'category', 'item_id', 'brand', 'item_name', 'supermarket', 'price']:
        if col not in df.columns:
            df[col] = '未分類' if col in ['cat1', 'category'] else ''

    # 清理超市名稱與價格
    df['supermarket'] = df['supermarket'].astype(str).str.upper().str.strip()
    df['supermarket'] = df['supermarket'].map(lambda x: SHOP_MAP.get(x, x))
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    
    # 保留標準 8 個欄位
    required_cols = ['date', 'cat1', 'category', 'item_id', 'brand', 'item_name', 'supermarket', 'price']
    return df.dropna(subset=['price'])[required_cols]

# ==========================================
# 步驟 A: 下載今日最新數據 (嘗試 CSV，若失敗則回退至 JSON)
# ==========================================
print("⏳ 正在下載消委會最新數據...")
csv_url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_zh-Hant.csv'
json_url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch.json'
headers = {'User-Agent': 'Mozilla/5.0'}

df_today = pd.DataFrame()

try:
    df_raw = pd.read_csv(csv_url, encoding='utf-8-sig', storage_options=headers)
    df_today = standardize_dataframe(df_raw, default_date=today_str)
    print("✅ 成功從官方 CSV 源抓取並標準化數據！")
except Exception as e:
    print(f"⚠️ CSV 下載失敗 ({e})，嘗試切換至 JSON 源...")
    try:
        res = requests.get(json_url, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        
        rows = []
        for item in data:
            for p in item.get('prices', []):
                rows.append({
                    'cat1': item.get('cat1'),
                    'category': item.get('cat2'),
                    'item_id': item.get('code'),
                    'brand': item.get('brand'),
                    'item_name': item.get('name'),
                    'supermarket': p.get('shop_name', p.get('shop')),
                    'price': p.get('price')
                })
        df_today = standardize_dataframe(pd.DataFrame(rows), default_date=today_str)
        print("✅ 成功從 JSON 源抓取數據！")
    except Exception as err:
        print(f"❌ 今日數據抓取失敗: {err}")

# ==========================================
# 步驟 B: 整合歷史數據 (3/8, 4/8 與舊 CSV) 並去重
# ==========================================
if os.path.exists(monthly_file_path):
    print(f"📦 正在整合並標準化既有的檔案: {monthly_file_path}")
    df_existing = pd.read_csv(monthly_file_path)
    df_existing_std = standardize_dataframe(df_existing)
    
    # 結合今日與過往數據
    if not df_today.empty:
        df_all = pd.concat([df_existing_std, df_today], ignore_index=True)
    else:
        df_all = df_existing_std
else:
    df_all = df_today

if not df_all.empty:
    # 去重邏輯：同一天、同產品、同超市，只保留最後一筆
    df_all.drop_duplicates(subset=['date', 'item_id', 'supermarket'], keep='last', inplace=True)
    df_all.sort_values(by=['date', 'item_id'], inplace=True)
    
    # 存檔
    df_all.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')
    print(f"🎉 成功完成整合與儲存！檔案路徑: {monthly_file_path}")
    print(f"📊 目前數據庫包含總行數: {len(df_all)}")
    print(f"📅 包含的日期版本: {sorted(df_all['date'].unique().tolist())}")
