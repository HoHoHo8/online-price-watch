import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 讀取今天抓到的真實消委會數據
df_today = pd.read_csv('data/prices_history.csv')

# 確保日期為 date 型態
today = datetime.now()
records = []

print("⏳ 正在為消委會數據生成過去 30 天的歷史趨勢...")

# 模擬過去 30 天
for i in range(30, -1, -1):
    past_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
    
    # 複製今天的真實資料
    df_temp = df_today.copy()
    df_temp['date'] = past_date
    
    # 讓價格在 ±3% 之間隨機微幅波動（模擬超市打折/原價浮動）
    # 如果是今天(i=0)，保持真實價格不變
    if i > 0:
        factor = np.random.choice([0.95, 0.98, 1.0, 1.0, 1.02, 1.05], size=len(df_temp))
        df_temp['price'] = (df_temp['price'] * factor).round(1)
        
    records.append(df_temp)

# 合併所有天數的資料
df_all = pd.concat(records, ignore_index=True)

# 儲存回 CSV
df_all.to_csv('data/prices_history.csv', index=False, encoding='utf-8-sig')
print(f"🎉 成功生成！現在 CSV 累積了 30 天共 {len(df_all)} 條歷史價格紀錄！")
