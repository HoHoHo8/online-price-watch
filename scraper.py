import os
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# 確保 data 資料夾存在
os.makedirs('data', exist_ok=True)

url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch.json'

print("⏳ 正在從消委會下載最新價格數據...")
try:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
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

# 輔助函式：安全提取多語言欄位 (優先取繁體中文)
def parse_multilingual(field):
    if isinstance(field, dict):
        return field.get('zh-Hant') or field.get('zh-Hans') or field.get('en') or ''
    elif isinstance(field, str):
        return field
    return ''

rows = []
for item in data:
    # 解析類別、品牌、貨品名稱（自動處理 Dict 物件）
    cat1 = parse_multilingual(item.get('cat1'))
    cat2 = parse_multilingual(item.get('cat2'))
    brand = parse_multilingual(item.get('brand'))
    item_name = parse_multilingual(item.get('name'))
    item_id = item.get('code', '')

    prices_list = item.get('prices', [])
    if isinstance(prices_list, list):
        for price_info in prices_list:
            if isinstance(price_info, dict):
                price = price_info.get('price')
                
                # 超市名稱同樣處理多語言
                raw_shop = price_info.get('shop_name', price_info.get('shop', ''))
                shop_name = parse_multilingual(raw_shop)

                if price is not None and price != '':
                    rows.append({
                        'date': today_str,
                        'cat1': cat1,
                        'category': cat2,
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
    # 刪除同日期舊數據（防止重複寫入爛數據）
    df_old = df_old[df_old['date'] != today_str]
    df_combined = pd.concat([df_old, df_today], ignore_index=True)
else:
    df_combined = df_today

df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')

print(f"🎉 成功寫入當月檔案: {monthly_file_path}")
print(f"📊 當月累積數據量：{len(df_combined)} 行")
