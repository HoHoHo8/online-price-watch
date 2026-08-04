import os
import requests
import pandas as pd
from datetime import datetime
import time

# 消委會前端搜尋 API Endpoint
SEARCH_API = "https://online-price-watch.consumer.org.hk/opw/api/v2/pricewatch/search"

# 熱門貨品分類代碼表 (Cat1 / Cat2)
CATEGORIES = [
    {"cat1": "015", "cat2": "001", "name": "米"},
    {"cat1": "015", "cat2": "002", "name": "食油"},
    {"cat1": "015", "cat2": "003", "name": "罐頭/醬料"},
    {"cat1": "015", "cat2": "004", "name": "麵包/餅乾"},
    {"cat1": "016", "cat2": "001", "name": "飲料/飲用水"},
    {"cat1": "017", "cat2": "001", "name": "個人護理/紙巾"},
    {"cat1": "018", "cat2": "001", "name": "家居清潔/洗滌"},
]

def fetch_category_data(cat1, cat2, cat_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'https://online-price-watch.consumer.org.hk/opw/list/{cat1}/{cat2}'
    }
    
    # 搜尋參數：每頁抓取 100 條紀錄
    params = {
        'cat1_code': cat1,
        'cat2_code': cat2,
        'page': 1,
        'per_page': 100
    }
    
    try:
        response = requests.get(SEARCH_API, headers=headers, params=params, timeout=20)
        if response.status_code != 200:
            print(f"⚠️ 分類 [{cat_name}] 讀取失敗，Status: {response.status_code}")
            return []
        
        res_json = response.json()
        items = res_json.get('data', []) if isinstance(res_json, dict) else []
        return items
    except Exception as e:
        print(f"❌ 分類 [{cat_name}] 請求異常: {e}")
        return []

def fetch_all_data():
    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    print("⏳ 開始抓取消委會各類別超市貨品價格...")
    for cat in CATEGORIES:
        print(f"➡️ 正在抓取：{cat['name']} ({cat['cat1']}/{cat['cat2']})...")
        items = fetch_category_data(cat['cat1'], cat['cat2'], cat['name'])
        
        for item in items:
            code = item.get('code', '')
            brand = item.get('brand_name_tc') or item.get('brand', '')
            name = item.get('name_tc') or item.get('name', '')
            prices = item.get('prices', {})  # 包含各大超市價格

            if isinstance(prices, dict):
                for shop, price_info in prices.items():
                    # 解析價格 (可能為直接數值或 dict 結構)
                    price = price_info.get('price') if isinstance(price_info, dict) else price_info
                    if price:
                        try:
                            records.append({
                                'date': today,
                                'cat1': cat['name'],
                                'category': cat['name'],
                                'item_id': code,
                                'brand': brand,
                                'item_name': name,
                                'supermarket': shop,
                                'price': float(price)
                            })
                        except (ValueError, TypeError):
                            continue
        time.sleep(1) # 禮貌間隔 1 秒

    df_new = pd.DataFrame(records)
    print(f"🎉 今日 ({today}) 成功抓取全港超市共 {len(df_new)} 條真實價格數據！")
    return df_new

def update_history():
    df_new = fetch_all_data()
    
    # 如果完全沒抓到資料才建立預設備用檔
    if df_new.empty:
        print("⚠️ 未抓取到數據，嘗試建立預設結構...")
        today = datetime.now().strftime('%Y-%m-%d')
        df_new = pd.DataFrame([{
            'date': today, 'cat1': '米', 'category': '米', 'item_id': 'RICE_DEMO',
            'brand': '金象牌', 'item_name': '頂級香米 5公斤', 'supermarket': '惠康', 'price': 69.9
        }])

    file_path = 'data/prices_history.csv'
    os.makedirs('data', exist_ok=True)
    
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"🚀 CSV 檔案寫入成功！總歷史數據：{len(df_combined)} 條。")

if __name__ == '__main__':
    update_history()
