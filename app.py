import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="超級市場貨品價格追蹤 Dashboard", layout="wide")

st.title("🛒 香港網上超市價格追蹤 & 趨勢分析")

# 讀取歷史資料
@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv('data/prices_history.csv')
    df['date'] = pd.to_datetime(df['date'])
    return df

try:
    df = load_data()
except Exception as e:
    st.error("未搵到歷史數據，請先運行 scraper.py！")
    st.stop()

# 側邊欄：篩選器
st.sidebar.header("🔍 篩選條件")
brands = st.sidebar.multiselect("選擇品牌", options=df['brand'].unique(), default=df['brand'].unique())
selected_df = df[df['brand'].isin(brands)]

items = st.sidebar.selectbox("選擇貨品", options=selected_df['item_name'].unique())
item_df = selected_df[selected_df['item_name'] == items]

# 核心功能：計算 DoD, WoW, MoM, YoY 價格變動
def calculate_metrics(data):
    latest_date = data['date'].max()
    latest_prices = data[data['date'] == latest_date]
    
    metrics = []
    for shop in data['supermarket'].unique():
        shop_data = data[data['supermarket'] == shop].sort_values('date')
        if shop_data.empty: continue
        
        curr_price = shop_data.iloc[-1]['price']
        
        # 輔助計算特定天數前的價格
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

# 1. 顯示價格比較表
st.subheader(f"📌 {items} - 現價及歷史變動分析 (截至 {item_df['date'].max().strftime('%Y-%m-%d')})")
metrics_df = calculate_metrics(item_df)
st.dataframe(metrics_df, use_container_width=True)

# 2. 顯示價格走勢圖 (Plotly 折線圖)
st.subheader("📈 歷史價格走勢圖")
fig = px.line(
    item_df, 
    x='date', 
    y='price', 
    color='supermarket',
    title=f"{items} 在各大超市的價格走勢",
    labels={'date': '日期', 'price': '價格 (HKD)', 'supermarket': '超市'},
    markers=True
)
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)
