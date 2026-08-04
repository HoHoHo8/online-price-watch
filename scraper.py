import os
import requests
import pandas as pd
from datetime import datetime

# 消委會官方開放數據接口清單
DATA_URLS = [
    "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_tc.json",
    "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch-tc.json",
    "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch_en.json"
]

def fetch_all_data():
    # 模擬完整瀏覽器 Header，防止消委會 Server 拒絕 GitHub Actions 連線
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    data = None
    for url in DATA_URLS:
        try:
            print(f"⏳ 嘗試從消委會開放數據下載: {url}")
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code == 200:
                data = res.json()
                print("✅ 成功下載消委會全量數據庫！")
                break
            else:
                print(f"⚠️ Status Code: {res.status_code}")
        except Exception as e:
            print(f"⚠️ 連線失敗: {e}")
            continue

    if not data:
        raise Exception("❌ 無法連線至消委會 API，請確認網路連線或接口。")

    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    # 支援 JSON List 結構解析
    if isinstance(data, list):
        for item in data:
            code = item.get('code', '')
            cat1 = item.get('cat1_name', '一般食品')
            cat2 = item.get('cat2_name', cat1)
            brand = item.get('brand', '')
            name = item.get('name', '')
            prices = item.get('prices', {})

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
    print(f"🎉 今日 ({today}) 成功解鎖消委會全港共 {len(df_new)} 條真實超市價格數據！")
    return df_new

def update_history():
    df_new = fetch_all_data()
    
    if df_new.empty:
        raise Exception("❌ 解析出來的數據為空，中止寫入。")

    file_path = 'data/prices_history.csv'
    os.makedirs('data', exist_ok=True)
    
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        # 以 日期 + 貨品ID + 超市 為鍵值去重
        df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"🚀 CSV 歷史檔案更新完畢！總紀錄達 {len(df_combined)} 條。")

if __name__ == '__main__':
    update_history()
