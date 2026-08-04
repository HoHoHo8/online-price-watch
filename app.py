import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="超級市場貨品價格追蹤 Dashboard", layout="wide")

st.title("🛒 香港網上超市價格追蹤 & 趨勢分析")

# 讀取歷史資料 (強迫關閉長時間快取，確保即時讀取最新 CSV)
@st.cache_data(ttl=10)
def load_data():
    df = pd.read_csv('data/prices_history.csv')
    df['date'] = pd.to_datetime(df['date'])
    
    # 相容性處理：如果 category 為空，使用 cat1
    if 'category' not in df.columns or df['category'].isnull().all():
        df['category'] = df['cat1']
        
    # 清理字串欄位空值
    df['brand'] = df['brand'].fillna('其他品牌')
    df['category'] = df['category'].fillna('一般食品')
    df['item_name'] = df['item_name'].fillna('未命名貨品')
    return df

try:
    df = load_data()
except Exception as e:
    st.error("未搵到歷史數據，請檢查 data/prices_history.csv！")
    st.stop()

# 側邊欄：多級篩選器
st.sidebar.header("🔍 篩選條件")

# 1. 類別篩選
categories = sorted(df['category'].dropna().unique().tolist())
selected_cat = st.sidebar.selectbox("1. 選擇貨品類別", options=["全部類別"] + categories)

df_filtered = df if selected_cat == "全部類別" else df[df['category'] == selected_cat]

# 2. 品牌篩選 (預設全選，方便搜尋)
brands = sorted(df_filtered['brand'].dropna().unique().tolist())
selected_brands = st.sidebar.multiselect("2. 選擇品牌 (可多選)", options=brands, default=brands)

df_filtered = df_filtered[df_filtered['brand'].isin(selected_brands)] if selected_brands else df_filtered

# 3. 貨品搜尋/選擇
items = sorted(df_filtered['item_name'].dropna().unique().tolist())

if not items:
    st.warning("⚠️ 找不到符合條件的貨品，請重新勾選品牌或類別！")
    st.stop()

selected_item = st.sidebar.selectbox("3. 選擇貨品", options=items)
item_df = df_filtered[df_filtered['item_name'] == selected_item]

# 核心功能：計算 DoD, WoW, MoM, YoY
def calculate_metrics(data):
    if data.empty:
        return pd.DataFrame()
        
    latest_date = data['date'].max()
    metrics = []
    
    for shop in data['supermarket'].unique():
        shop_data = data[data['supermarket'] == shop].sort_values('date')
        if shop_data.empty:
            continue
        
        curr_price = shop_data.iloc[-1]['price']
        
        def get_past_price(days):
            target_date = latest_date - timedelta(days=days)
            past_data = shop_data[shop_data['date'] <= target_date]
            return past_data.iloc[-1]['price'] if not past_data.empty else None

        dod = ((curr_price - get_past_price(1)) / get_past_price(1) * 100) if get_past_price(1) else None
        wow = ((curr_price - get_past_price(7)) / get_past_price(7) * 100) if get_past_price(7) else None
        mom = ((curr_price - get_past_price(30)) / get_past_price(30) * 100) if get_past_price(30) else None
        yoy = ((curr_price - get_past_price(365)) / get_past_price(365) * 100) if get_past_price(365) else None
        
        metrics.append({
            '超市': shop,
            '最新售價 ($)': f"${curr_price:.2f}",
            'DoD (按日)': f"{dod:+.2f}%" if dod is not None else "N/A",
            'WoW (按周)': f"{wow:+.2f}%" if wow is not None else "N/A",
            'MoM (按月)': f"{mom:+.2f}%" if mom is not None else "N/A",
            'YoY (按年)': f"{yoy:+.2f}%" if yoy is not None else "N/A"
        })
    return pd.DataFrame(metrics)

# 顯示價格數據與圖表
if not item_df.empty and pd.notna(item_df['date'].max()):
    latest_date_str = item_df['date'].max().strftime('%Y-%m-%d')
    st.subheader(f"📌 {selected_item} - 現價及歷史變動分析 (截至 {latest_date_str})")
    
    metrics_df = calculate_metrics(item_df)
    st.dataframe(metrics_df, use_container_width=True)

    # 折線走勢圖
    st.subheader("📈 歷史價格走勢圖")
    fig = px.line(
        item_df, 
        x='date', 
        y='price', 
        color='supermarket',
        title=f"{selected_item} 在各大超市的價格走勢",
        labels={'date': '日期', 'price': '價格 (HKD)', 'supermarket': '超市'},
        markers=True
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
