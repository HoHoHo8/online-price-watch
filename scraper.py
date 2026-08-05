import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

os.makedirs('data', exist_ok=True)

hkt_timezone = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt_timezone)
today_str = now_hkt.strftime('%Y-%m-%d')
month_str = now_hkt.strftime('%Y_%m')
monthly_file_path = f'data/prices_{month_str}.csv'

print(f"📅 當前香港日期: {today_str}")

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
    'HKTVMALL': 'HKTVmall',
    'DAISO': 'Daiso',
    'DCH': '大昌食品'
}

def process_scraped_df(df_input, default_date=today_str):
    df = df_input.copy()
    df.columns = [str(c).strip() for c in df.columns]
    
    rename_dict = {}
    for col in df.columns:
        c_lower = col.lower()
        if '分類1' in col or c_lower == 'cat1':
            rename_dict[col] = 'cat1'
        elif '分類2' in col or c_lower == 'category':
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
            rename_dict[col] = 'offers'  # 👈 新增優惠欄位對照

    df.rename(columns=rename_dict, inplace=True)
    
    if 'date' not in df.columns:
        df['date'] = default_date
    else:
        df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True).dt.strftime('%Y-%m-%d')
        df['date'] = df['date'].fillna(default_date)

    if 'supermarket' in df.columns:
        df['supermarket'] = df['supermarket'].fillna('').astype(str).str.strip().str.upper()
        df['supermarket'] = df['supermarket'].apply(lambda x: SHOP_MAP.get(x, x if x != '' else '其他超市'))
    else:
        df['supermarket'] = '其他超市'

    # 清理優惠欄位（若為空則填補無優惠）
    if 'offers' in df.columns:
        df['offers'] = df['offers'].fillna('—').astype(str).str.strip()
        df['offers'] = df['offers'].replace({'': '—', 'nan': '—', 'None': '—'})
    else:
        df['offers'] = '—'

    for col in ['cat1', 'category', 'item_id', 'brand', 'item_name']:
        if col not in df.columns:
            df[col] = '未分類' if 'cat' in col else ''
        else:
            df[col] = df[col].fillna('').astype(str).str.strip()

    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    
    # 包含 offers 共 9 個欄位
    required_cols = ['date', 'cat1', 'category', 'item_id', 'brand', 'item_name', 'supermarket', 'price', 'offers']
    return df.dropna(subset=['price'])[required_cols]

# 下載與處理
csv_url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_zh-Hant.csv'
headers = {'User-Agent': 'Mozilla/5.0'}

try:
    df_raw = pd.read_csv(csv_url, encoding='utf-8-sig', storage_options=headers)
    df_today = process_scraped_df(df_raw, default_date=today_str)
except Exception as e:
    print(f"❌ 下載失敗: {e}")
    exit(1)

if os.path.exists(monthly_file_path):
    df_existing = pd.read_csv(monthly_file_path)
    df_existing_clean = process_scraped_df(df_existing)
    df_combined = pd.concat([df_existing_clean, df_today], ignore_index=True)
else:
    df_combined = df_today

df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'], keep='last', inplace=True)
df_combined.sort_values(by=['date', 'item_id'], inplace=True)
df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')
print(f"🎉 成功寫入包含優惠資訊的檔案: {monthly_file_path}")
