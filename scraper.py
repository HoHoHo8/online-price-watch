import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# 確保 data 資料夾存在
os.makedirs('data', exist_ok=True)

url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch.json'

print("⏳ 正在從消委會下載最新價格數據...")

# 設定偽裝 Headers 避開 403 阻擋
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://online-price-watch.consumer.org.hk/',
    'Origin': 'https://online-price-watch.consumer.org.hk'
}

try:
    session = requests.Session()
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    print("✅ 數據下載成功！")
except Exception as e:
    print(f"❌ 下載數據失敗: {e}")
    exit(1)

# 強制使用香港時間 (UTC+8)
hkt_timezone = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt_timezone)

today_str = now_hkt.strftime('%Y-%m-%d')
month_str = now_hkt.strftime('%Y_%m')
monthly_file_path = f'data/prices_{month_str}.csv'

print(f"📅 當前香港日期: {today_str}")

# 輔助函式：安全提取多語言與多種可能 Key 的欄位
def parse_field(item, keys):
    for key in keys:
        val = item.get(key)
        if val:
            if isinstance(val, dict):
                res = val.get('zh-Hant') or val.get('zh-Hans') or val.get('en') or ''
                if res:
                    return res
            elif isinstance(val, str) and val.strip():
                return val.strip()
    return ''

rows = []
for item in data:
    # 針對類別嘗試多種常見的 Key 名稱 (cat1, category1, cat_name1 等)
    cat1 = parse_field(item, ['cat1', 'category1', 'cat1_name', 'main_category'])
    cat2 = parse_field(item, ['cat2', 'category2', 'category', 'cat2_name', 'sub_category'])
    
    brand = parse_field(item, ['brand', 'brand_name'])
    item_name = parse_field(item, ['name', 'item_name', 'title'])
    item_id = item.get('code', item.get('id', ''))

    prices_list = item.get('prices', [])
    if isinstance(prices_list, list):
        for price_info in prices_list:
            if isinstance(price_info, dict):
                price = price_info.get('price')
                
                # 解析超市名稱
                shop_name = parse_field(price_info, ['shop_name', 'shop', 'supermarket'])

                if price is not None and price != '':
                    rows.append({
                        'date': today_str,
                        'cat1': cat1 if cat1 else '未分類主類別',
                        'category': cat2 if cat2 else '未分類子類別',
                        'item_id': item_id,
                        'brand': brand,
                        'item_name': item_name,
                        'supermarket': shop_name,
                        'price': price
                    })

df_today = pd.DataFrame(rows)

if df_today.empty:
    print("⚠️ 警告：今日無任何數據下載成功，終止寫入！")
    exit(1)

print(f"✅ 今日成功提取 {len(df_today)} 筆價格數據！")

# 追加寫入當月專屬 CSV
if os.path.exists(monthly_file_path):
    df_old = pd.read_csv(monthly_file_path)
    # 刪除同日期舊數據（防止重複寫入）
    df_old = df_old[df_old['date'] != today_str]
    df_combined = pd.concat([df_old, df_today], ignore_index=True)
else:
    df_combined = df_today

df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')

print(f"🎉 成功寫入當月檔案: {monthly_file_path}")
print(f"📊 當月累積數據量：{len(df_combined)} 行")
