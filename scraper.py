import os
import requests
import pandas as pd
from datetime import datetime

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

today_str = datetime.now().strftime('%Y-%m-%d')
month_str = datetime.now().strftime('%Y_%m')
monthly_file_path = f'data/prices_{month_str}.csv'

rows = []
for item in data:
    cat1 = item.get('cat1', '')
    cat2 = item.get('cat2', '')
    item_id = item.get('code', '')
    brand = item.get('brand', '')
    item_name = item.get('name', '')
    
    # 修正重點：prices 是列表 (List)，遍歷每個超市字典
    prices_list = item.get('prices', [])
    if isinstance(prices_list, list):
        for price_info in prices_list:
            if isinstance(price_info, dict):
                price = price_info.get('price')
                shop_name = price_info.get('shop_name', price_info.get('shop', ''))
                
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

# 追加寫入當月專屬 CSV
if os.path.exists(monthly_file_path):
    df_old = pd.read_csv(monthly_file_path)
    df_combined = pd.concat([df_old, df_today], ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'], keep='last')
else:
    df_combined = df_today

df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')

print(f"🎉 成功寫入當月檔案: {monthly_file_path}")
print(f"📊 當月累積數據量：{len(df_combined)} 行")
