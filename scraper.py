import requests
import pandas as pd
from datetime import datetime
import os

# 1. 消委會「米」類別 JSON 資料接口 (015/001)
URL = "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_en.json" # 或使用相應類別 API

def fetch_data():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(URL, headers=headers)
    data = response.json()
    
    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    # 拆解資料結構（按消委會 JSON 格式調整）
    for item in data:
        # 只過濾米/食物相關 (分類 ID: 015/001)
        if item.get('cat2_code') == '001':
            code = item.get('code')
            brand = item.get('brand')
            name = item.get('name')
            
            # 遍歷不同超市價格 (惠康, 百佳, Market Place 等)
            for shop, price in item.get('prices', {}).items():
                if price:
                    records.append({
                        'date': today,
                        'item_id': code,
                        'brand': brand,
                        'item_name': name,
                        'supermarket': shop,
                        'price': float(price)
                    })
                    
    df_new = pd.DataFrame(records)
    return df_new

def update_history():
    df_new = fetch_data()
    file_path = 'data/prices_history.csv'
    
    os.makedirs('data', exist_ok=True)
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        # 去重，避免同一天重複爬取
        df_combined = pd.concat([df_old, df_new]).drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False)
    print(f"[{datetime.now()}] 數據已更新，共 {len(df_combined)} 條歷史紀錄。")

if __name__ == '__main__':
    update_history()
