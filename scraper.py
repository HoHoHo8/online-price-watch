import os
import requests
import pandas as pd
from datetime import datetime

# 消委會全量開放數據 API 備用網址清單
DATA_URLS = [
    "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch-tc.json",  # 官方最新全量 JSON (連字號)
    "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_tc.json",  # 備用底線網址
    "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_en.json"   # 備用英文全量 JSON
]

def fetch_all_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    data = None
    # 遍歷網址，直到成功取得 JSON 資料
    for url in DATA_URLS:
        try:
            print(f"⏳ 嘗試從消委會下載數據: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                print("✅ 成功連線並取得消委會全量數據！")
                break
        except Exception as e:
            print(f"⚠️ 連線 {url} 失敗: {e}")
            continue

    if not data:
        raise Exception("❌ 所有消委會 API 接口均連線失敗，請檢查網路或 API 是否改版。")

    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    # 解析消委會全量貨品 JSON
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
    print(f"🎉 今日 ({today}) 成功解析全港消委會共 {len(df_new)} 條超市價格數據！")
    return df_new

def update_history():
    df_new = fetch_all_data()
    
    if df_new.empty:
        raise Exception("❌ 解析出來的數據庫為空，取消更新。")

    file_path = 'data/prices_history.csv'
    os.makedirs('data', exist_ok=True)
    
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"🚀 CSV 檔案更新完成！累積歷史數據已達 {len(df_combined)} 條。")

if __name__ == '__main__':
    update_history()
