import os
import requests
import pandas as pd
import json
from datetime import datetime, timezone, timedelta

# 確保 data 資料夾存在
os.makedirs('data', exist_ok=True)

url = 'https://online-price-watch.consumer.org.hk/opw/opendata/pricewatch.json'

print("⏳ 正在從消委會下載最新價格數據...")

# 設定偽裝 Headers 避開 403 阻擋
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://online-price-watch.consumer.org.hk/',
    'Origin': 'https://online-price-watch.consumer.org.hk'
}

try:
    session = requests.Session()
    response = session.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    print("✅ 數據下載成功！")
except Exception as e:
    print(f"❌ 下載數據失敗: {e}")
    exit(1)

# 印出第 1 筆數據結構，供 GitHub Actions Log 查驗真實欄位名稱
if data and len(data) > 0:
    print("\n🔍 --- [DEBUG Log] 第一筆商品數據結構預覽 ---")
    print(json.dumps(data[0], ensure_ascii=False, indent=2)[:1200])
    print("-----------------------------------------\n")

# 香港常見超市代碼對照表 (當 API 僅傳回代碼時自動轉換)
SHOP_MAP = {
    'WELLCOME': '惠康',
    'PARKNSHOP': '百佳',
    'MARKETPLACE': 'Market Place',
    'AEON': 'AEON',
    'TASTE': 'TASTE',
    'FUSION': 'FUSION',
    'DONKI': 'DON DON DONKI',
    'DONGURI': 'DON DON DONKI',
    'MANNINGS': '萬寧',
    'WATSONS': '屈臣氏',
    'HKTVMALL': 'HKTVmall',
    'DAISO': 'Daiso',
    'DCH': '大昌食品'
}

# 強制使用香港時間 (UTC+8)
hkt_timezone = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt_timezone)

today_str = now_hkt.strftime('%Y-%m-%d')
month_str = now_hkt.strftime('%Y_%m')
monthly_file_path = f'data/prices_{month_str}.csv'

print(f"📅 當前香港日期: {today_str}")

# 萬能文字提取函式
def extract_text(obj):
    if not obj:
        return ''
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, dict):
        # 1. 優先取中文/英文語言 Key
        for lang in ['zh-Hant', 'zh_Hant', 'zh-HK', 'zh_HK', 'zh-Hans', 'zh', 'en', 'name_zh', 'title_zh']:
            if lang in obj:
                res = extract_text(obj[lang])
                if res:
                    return res
        # 2. 尋找 name / title / label 鍵
        for sub_key in ['name', 'title', 'label', 'text', 'value', 'zh_name']:
            if sub_key in obj:
                res = extract_text(obj[sub_key])
                if res:
                    return res
        # 3. 遍歷非 code/id 欄位
        for k, v in obj.items():
            if k.lower() not in ['code', 'id', 'key', 'shop_code']:
                res = extract_text(v)
                if res:
                    return res
    if isinstance(obj, list):
        for elem in obj:
            res = extract_text(elem)
            if res:
                return res
    return ''

def get_smart_field(item, keys):
    for key in keys:
        if key in item and item[key] is not None:
            val = extract_text(item[key])
            if val:
                return val
    return ''

rows = []
for item in data:
    # 1. 解析主類別 (Cat1)
    cat1 = get_smart_field(item, [
        'cat1_name', 'cat1_zh', 'cat1_title', 'cat1', 'category1', 'main_category', 'cat_1', 'cat1Name'
    ])
    
    # 2. 解析子類別 (Category / Cat2)
    cat2 = get_smart_field(item, [
        'cat2_name', 'cat2_zh', 'cat2_title', 'cat2', 'category2', 'sub_category', 'cat_2', 'cat2Name', 'category'
    ])
    
    # 若類別為列表格式 (e.g. "categories": [{"name": "主類"}, {"name": "子類"}])
    if (not cat1 or not cat2) and 'categories' in item and isinstance(item['categories'], list):
        cats = item['categories']
        if len(cats) > 0 and not cat1:
            cat1 = extract_text(cats[0])
        if len(cats) > 1 and not cat2:
            cat2 = extract_text(cats[1])

    brand = get_smart_field(item, ['brand', 'brand_name', 'brand_zh'])
    item_name = get_smart_field(item, ['name', 'item_name', 'title', 'name_zh'])
    item_id = str(item.get('code', item.get('id', '')))

    prices_list = item.get('prices', [])
    if isinstance(prices_list, list):
        for price_info in prices_list:
            if isinstance(price_info, dict):
                price = price_info.get('price')
                
                # 解析超市名稱
                shop_name = get_smart_field(price_info, [
                    'shop_name', 'shop_zh', 'shopName', 'shop', 'supermarket', 'store', 'store_name'
                ])
                
                # 若無直接名稱，嘗試用 shop_code 查對照表
                if not shop_name or shop_name == '其他超市':
                    raw_code = str(price_info.get('shop_code', price_info.get('shop', ''))).upper()
                    shop_name = SHOP_MAP.get(raw_code, raw_code if raw_code else '其他超市')

                if price is not None and price != '':
                    rows.append({
                        'date': today_str,
                        'cat1': cat1 if cat1 else '一般主類別',
                        'category': cat2 if cat2 else '一般子類別',
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
    df_old = df_old[df_old['date'] != today_str]
    df_combined = pd.concat([df_old, df_today], ignore_index=True)
else:
    df_combined = df_today

df_combined.to_csv(monthly_file_path, index=False, encoding='utf-8-sig')

print(f"🎉 成功寫入當月檔案: {monthly_file_path}")
print(f"📊 當月累積數據量：{len(df_combined)} 行")
