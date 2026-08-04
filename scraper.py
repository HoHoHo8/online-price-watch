import os
import requests
import pandas as pd
from datetime import datetime

# 確保 data 資料夾存在
os.makedirs('data', exist_ok=True)

# 1. 消委會 Open Data API
url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch.json'

print("⏳ 正在從消委會下載最新價格數據...")
response = requests.get(url)
data = response.json()

# 2. 解析 JSON
today_str = datetime.now().strftime('%Y-%m-%d')
month_str = datetime.now().strftime('%Y_%m')  # 例如 "2026_08"

# 動態按當月命名檔案，例如: data/prices_2026_08.csv
monthly_file_path = f'data/prices_{month_str}.csv'

rows = []
for item in data:
    cat1 = item.get('cat1', '')
    cat2 = item.get('cat2', '')
    item_id = item.get('code', '')
    brand = item.get('brand', '')
    item_name = item.get('name', '')
    
    # 遍歷各超市價格
    for shop_code, price_info in item.get('prices', {}).items():
        price = price_info.get('price')
        shop_name = price_info.get('shop_name', shop_code)
        
        if price is not None:
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

# 3. 追加寫入當月專屬 CSV (如果檔案存在就讀取並追加，不存在就創建)
if os.path.exists(monthly_file_path):
    df_old = pd.read_csv(monthly_file_path)
    df_combined = pd.concat([df_old, df_today], ignore_index=True)
    # 依照日期、貨品、超市去重，避免重複抓取
    df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'], keep='last')
else:
    df_combined = df_today

df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')

print(f"🎉 成功寫入當月檔案: {monthly_file_path}")
print(f"📊 當月累積數據量：{len(df_combined)} 行")
