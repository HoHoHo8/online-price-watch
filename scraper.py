import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# 1. 確保儲存目錄存在
os.makedirs('data', exist_ok=True)

# 2. 強制使用香港時間 (UTC+8)
hkt_timezone = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt_timezone)
today_str = now_hkt.strftime('%Y-%m-%d')
month_str = now_hkt.strftime('%Y_%m')
monthly_file_path = f'data/prices_{month_str}.csv'

print(f"📅 當前香港日期: {today_str}")

# 3. 超市代碼對映字典
SHOP_MAP = {
    'WELLCOME': '惠康',
    'PARKNSHOP': '百佳',
    'JASONS': 'Market Place / Jasons',
    'MARKETPLACE': 'Market Place',
    'AEON': 'AEON',
    'TASTE': 'TASTE',
    'FUSION': 'FUSION',
    'DONKI': 'DON DON DONKI',
    'DONGURI': 'DON DON DONKI',
    'MANNINGS': '萬寧',
    'WATSONS': '屈臣氏',
    'HKTVMALL': 'HKTVmall',
    'DAISO': 'Daiso',
    'DCH': '大昌食品'
}

def process_scraped_df(df_input, default_date=today_str):
    """
    清洗數據、格式化日期 (自動智能解析，防止 YYYY-MM-DD 被誤改)
    """
    df = df_input.copy()
    if df.empty:
        return pd.DataFrame()
    
    # 1. 欄位標頭去空白並去除重複欄位名
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    
    # 2. 重命名欄位對照
    rename_dict = {}
    for col in df.columns:
        c_lower = col.lower()
        if '分類1' in col or c_lower == 'cat1':
            rename_dict[col] = 'cat1'
        elif '分類2' in col or '分類3' in col or c_lower in ['category', 'cat2']:
            rename_dict[col] = 'category'
        elif '編號' in col or c_lower in ['item_id', 'code', 'id']:
            rename_dict[col] = 'item_id'
        elif '品牌' in col or c_lower == 'brand':
            rename_dict[col] = 'brand'
        elif '名稱' in col or c_lower in ['item_name', 'name', 'title']:
            rename_dict[col] = 'item_name'
        elif '超市' in col or 'shop' in c_lower or 'store' in c_lower or c_lower == 'supermarket':
            rename_dict[col] = 'supermarket'
        elif '價格' in col or '價錢' in col or c_lower == 'price':
            rename_dict[col] = 'price'
        elif '優惠' in col or 'offer' in c_lower or 'promo' in c_lower:
            rename_dict[col] = 'offers'

    df.rename(columns=rename_dict, inplace=True)
    df = df.loc[:, ~df.columns.duplicated()]
    
    # 3. 關鍵修正：採用 format='mixed' 智能解析，不再加 dayfirst
    if 'date' not in df.columns:
        df['date'] = default_date
    else:
        df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce').dt.strftime('%Y-%m-%d')
        df['date'] = df['date'].fillna(default_date)

    # 4. 超市代碼轉中文
    if 'supermarket' in df.columns:
        df['supermarket'] = df['supermarket'].fillna('').astype(str).str.strip().str.upper()
        df['supermarket'] = df['supermarket'].apply(lambda x: SHOP_MAP.get(x, x if x != '' else '其他超市'))
    else:
        df['supermarket'] = '其他超市'

    # 5. 優惠資訊清洗
    if 'offers' in df.columns:
        df['offers'] = df['offers'].fillna('—').astype(str).str.strip()
        df['offers'] = df['offers'].replace({'': '—', 'nan': '—', 'None': '—'})
    else:
        df['offers'] = '—'

    # 6. 基礎文字欄位清洗
    for col in ['cat1', 'category', 'item_id', 'brand', 'item_name']:
        if col not in df.columns:
            df[col] = '未分類' if 'cat' in col else ''
        else:
            df[col] = df[col].fillna('').astype(str).str.strip()

    # 7. 價格轉數值
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    
    required_cols = ['date', 'cat1', 'category', 'item_id', 'brand', 'item_name', 'supermarket', 'price', 'offers']
    return df.dropna(subset=['price'])[required_cols]

# ==========================================
# 4. 下載消委會數據
# ==========================================
csv_url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_zh-Hant.csv'
headers = {'User-Agent': 'Mozilla/5.0'}

print("⏳ 正在從消委會下載最新官方 CSV 數據...")

try:
    df_raw = pd.read_csv(csv_url, encoding='utf-8-sig', storage_options=headers)
    df_today = process_scraped_df(df_raw, default_date=today_str)
    print("✅ 今日最新數據下載與解析成功！")
except Exception as e:
    print(f"❌ 下載消委會數據失敗: {e}")
    exit(1)

# ==========================================
# 5. 讀取並整合歷史檔案
# ==========================================
df_existing_clean = pd.DataFrame()

if os.path.exists(monthly_file_path):
    print(f"📦 正在讀取歷史檔案: {monthly_file_path}")
    try:
        df_existing = pd.read_csv(monthly_file_path)
        if not df_existing.empty:
            df_existing_clean = process_scraped_df(df_existing)
    except pd.errors.EmptyDataError:
        print(f"⚠️ {monthly_file_path} 為空檔案，將由今日最新數據覆蓋。")
    except Exception as e:
        print(f"⚠️ 讀取舊數據錯誤: {e}")

if not df_existing_clean.empty:
    df_combined = pd.concat([df_existing_clean, df_today], ignore_index=True)
else:
    df_combined = df_today

df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'], keep='last', inplace=True)
df_combined.sort_values(by=['date', 'item_id'], inplace=True)

df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')

print(f"🎉 數據整合完成！存檔路徑: {monthly_file_path}")
print(f"📊 數據庫總行數: {len(df_combined)}")
