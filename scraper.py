import os
import requests
import pandas as pd
from datetime import datetime

# 消委會官方 DATA.GOV.HK 正確全量數據接口
FULL_DATA_URL = "https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch.json"

# 超市代碼轉中文對照表
SUPERMARKET_MAP = {
    'WELLCOME': '惠康',
    'PARKNSHOP': '百佳',
    'AEON': 'AEON',
    'JASONS': 'Market Place / Market Place by Jasons',
    'DONGURI': 'DON DON DONKI',
    'DahShing': '大昌食品',
    'DCH': '大昌食品'
}

def get_text(obj, prefer_lang='zh-Hant'):
    """ 輔助函式：從消委會多語言物件 {"en": "...", "zh-Hant": "..."} 中提取中文 """
    if isinstance(obj, dict):
        return obj.get(prefer_lang) or obj.get('en') or next(iter(obj.values()), '')
    elif isinstance(obj, str):
        return obj
    return ''

def fetch_all_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    print("⏳ 正在從消委會下載全量數據 (pricewatch.json)...")
    try:
        response = requests.get(FULL_DATA_URL, headers=headers, timeout=40)
        response.raise_for_status()
        data = response.json()
        print("✅ 成功連線並取得消委會全量數據！")
    except Exception as e:
        print(f"❌ 下載失敗: {e}")
        return pd.DataFrame()

    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    # 精準解析消委會全量 JSON 結構
    if isinstance(data, list):
        for item in data:
            code = item.get('code', '')
            cat1 = get_text(item.get('cat1Name', '一般食品'))
            cat2 = get_text(item.get('cat2Name', cat1))
            brand = get_text(item.get('brand', '其他品牌'))
            name = get_text(item.get('name', '未命名貨品'))
            
            prices_list = item.get('prices', [])

            # 解析價格陣列 [{'supermarketCode': 'WELLCOME', 'price': '16.90'}, ...]
            if isinstance(prices_list, list):
                for price_entry in prices_list:
                    if isinstance(price_entry, dict):
                        shop_code = price_entry.get('supermarketCode', '')
                        price_val = price_entry.get('price')
                        
                        shop_name = SUPERMARKET_MAP.get(shop_code, shop_code)
                        
                        if price_val and shop_name:
                            try:
                                records.append({
                                    'date': today,
                                    'cat1': cat1,
                                    'category': cat2,
                                    'item_id': code,
                                    'brand': brand,
                                    'item_name': name,
                                    'supermarket': shop_name,
                                    'price': float(price_val)
                                })
                            except (ValueError, TypeError):
                                continue

    df_new = pd.DataFrame(records)
    print(f"🎉 今日 ({today}) 成功解鎖全港超市共 {len(df_new)} 條真實價格數據！")
    return df_new

def update_history():
    df_new = fetch_all_data()
    
    if df_new.empty:
        print("⚠️ 未能取得數據，取消更新。")
        return

    file_path = 'data/prices_history.csv'
    os.makedirs('data', exist_ok=True)
    
    if os.path.exists(file_path):
        df_old = pd.read_csv(file_path)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['date', 'item_id', 'supermarket'])
    else:
        df_combined = df_new
        
    df_combined.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"🚀 CSV 檔案更新完成！累積歷史紀錄達 {len(df_combined)} 條。")

if __name__ == '__main__':
    update_history()
