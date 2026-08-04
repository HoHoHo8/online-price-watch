import os
import requests
import pandas as pd
from datetime import datetime

# 消委會官方「全量中文 Open Data」JSON 接口
FULL_DATA_URL = "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_tc.json"

def fetch_all_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    print("⏳ 正在從消委會下載全量超市價格數據...")
    response = requests.get(FULL_DATA_URL, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    # 遍歷消委會所有貨品
    if isinstance(data, list):
        for item in data:
            code = item.get('code', '')
            cat1 = item.get('cat1_name', '一般食品')  # 大類別
            cat2 = item.get('cat2_name', '其他')      # 中類別
            brand = item.get('brand', '')            # 品牌
            name = item.get('name', '')              # 貨品名稱
            prices = item.get('prices', {})          # 各超市價格

            if isinstance(prices, dict):
                for shop, price in prices.items():
                    if price:
                        try:
                            records.append({
                                'date': today,
                                'cat1': cat1,
                                'category': cat2,
                                'item_id': code,
                                'brand': brand,
                                'item_name': name,
                                'supermarket': shop,
                                'price': float(price)
                            })
                        except (ValueError, TypeError):
                            continue

    df_new = pd.DataFrame(records)
    print(f"✅ 成功抓取今日 ({today}) 全港消委會共 {len(df_new)} 條價格數據！")
    return df_new

def update_history():
    df_new = fetch_all_data()
    
    if df_new.empty:
        raise Exception("❌ 未能取得任何數據！")

    file_path = 'data/prices_history.csv'
    os.makedirs('data', exist_ok=True)
    
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"🎉 歷史數據檔案更新成功！累積紀錄達 {len(df_combined)} 條。")

if __name__ == '__main__':
    update_history()
