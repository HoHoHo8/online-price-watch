import os
import requests
import pandas as pd
from datetime import datetime

# 消委會開放數據 API 網址 (米/食品等類別)
URL = "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_en.json"

def fetch_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(URL, headers=headers, timeout=30)
        response.raise_for_status()  # 檢查 HTTP Status 是否為 200
        data = response.json()
    except Exception as e:
        print(f"❌ 抓取資料失敗: {e}")
        # 如果 request 失敗，回傳空 DataFrame 避免程式 Crash
        return pd.DataFrame()

    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    # 解析 JSON
    if isinstance(data, list):
        for item in data:
            # 判斷是否有對應的欄位
            code = item.get('code', '')
            brand = item.get('brand', '')
            name = item.get('name', '')
            prices = item.get('prices', {})

            if isinstance(prices, dict):
                for shop, price in prices.items():
                    if price:
                        try:
                            records.append({
                                'date': today,
                                'item_id': code,
                                'brand': brand,
                                'item_name': name,
                                'supermarket': shop,
                                'price': float(price)
                            })
                        except ValueError:
                            continue

    df_new = pd.DataFrame(records)
    print(f"✅ 成功抓取 {len(df_new)} 條今天 ({today}) 的數據")
    return df_new

def update_history():
    df_new = fetch_data()
    
    if df_new.empty:
        print("⚠️ 未能取得新數據，結束更新。")
        return

    file_path = 'data/prices_history.csv'
    os.makedirs('data', exist_ok=True)
    
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_combined = pd.concat([df_old, df_new]).drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False)
    print(f"🎉 歷史數據已更新！總共 {len(df_combined)} 條紀錄。")

if __name__ == '__main__':
    update_history()
