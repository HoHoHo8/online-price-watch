import glob
import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. 頁面設定
st.set_page_config(page_title="香港網上超市價格追蹤系統", layout="wide")

# ---------------------------------------------------------
# 🔒 密碼登入機制設定
# ---------------------------------------------------------
# 💡 請在下方修改為你自訂的登入密碼
APP_PASSWORD = "zakuissmart_168"  # <--- 請修改這裡的密碼！

# 初始化登入狀態
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 登入頁面 UI
def login_page():
    st.title("🔒 超市價格追蹤系統 - 身份驗證")
    st.markdown("本系統僅供內部/個人研究使用，請輸入存取密碼。")
    
    password_input = st.text_input("請輸入密碼", type="password")
    if st.button("登入"):
        if password_input == APP_PASSWORD:
            st.session_state.authenticated = True
            st.success("密碼正確！正在進入系統...")
            st.rerun()
        else:
            st.error("❌ 密碼不正確，請重新輸入。")

# 若未通過驗證，停止載入後續 UI
if not st.session_state.authenticated:
    login_page()
    st.stop()

# ---------------------------------------------------------
# 🔓 通過驗證後的 Dashboard 主體
# ---------------------------------------------------------

# 側邊欄：登出按鈕
st.sidebar.title("👤 使用者權限")
if st.sidebar.button("🚪 安全登出"):
    st.session_state.authenticated = False
    st.rerun()

st.sidebar.markdown("---")

st.title("🛒 香港網上超市價格追蹤 & 趨勢分析")

# 讀取歷史資料 (自動讀取 data/*.csv)
@st.cache_data(ttl=10)
def load_data():
    csv_files = glob.glob('data/*.csv')
    if not csv_files:
        raise FileNotFoundError("未在 data/ 資料夾中找到任何 CSV 數據檔案！")
        
    df_list = [pd.read_csv(f) for f in csv_files]
    df = pd.concat(df_list, ignore_index=True)
    
    # 支援混合日期格式
    df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=False)
    
    # 欄位空值補全
    if 'cat1' not in df.columns:
        df['cat1'] = '一般主類別'
    if 'category' not in df.columns:
        df['category'] = df['cat1']
        
    df['cat1'] = df['cat1'].fillna('未分類主類別')
    df['category'] = df['category'].fillna('未分類子類別')
    df['brand'] = df['brand'].fillna('其他品牌')
    df['item_name'] = df['item_name'].fillna('未命名貨品')
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    
    return df.dropna(subset=['price', 'date'])

try:
    df = load_data()
except Exception as e:
    st.error(f"未搵到歷史數據或格式有誤，請檢查 data/ 資料夾！錯誤訊息: {e}")
    st.stop()

# 側邊欄：分頁選單
page = st.sidebar.radio("📌 請選擇分析功能", ["單一貨品深度追蹤", "同類別貨品價格比較 (Cat1 / Category)"])
st.sidebar.markdown("---")

# ==========================================
# 頁面 1：單一貨品深度追蹤
# ==========================================
if page == "單一貨品深度追蹤":
    st.sidebar.header("🔍 篩選條件")

    # 1. 類別篩選
    categories = sorted(df['category'].dropna().unique().tolist())
    selected_cat = st.sidebar.selectbox("1. 選擇貨品類別", options=["全部類別"] + categories)

    df_filtered = df if selected_cat == "全部類別" else df[df['category'] == selected_cat]

    # 2. 品牌篩選
    brands = sorted(df_filtered['brand'].dropna().unique().tolist())
    selected_brands = st.sidebar.multiselect("2. 選擇品牌 (可多選)", options=brands, default=brands)

    df_filtered = df_filtered[df_filtered['brand'].isin(selected_brands)] if selected_brands else df_filtered

    # 3. 貨品選擇
    items = sorted(df_filtered['item_name'].dropna().unique().tolist())

    if not items:
        st.warning("⚠️ 找不到符合條件的貨品，請重新勾選品牌或類別！")
        st.stop()

    selected_item = st.sidebar.selectbox("3. 選擇貨品", options=items)
    item_df = df_filtered[df_filtered['item_name'] == selected_item]

    # 計算變動指標
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

    if not item_df.empty:
        latest_date_str = item_df['date'].max().strftime('%Y-%m-%d')
        st.subheader(f"📌 {selected_item} - 現價及歷史變動 (截至 {latest_date_str})")
        
        metrics_df = calculate_metrics(item_df)
        st.dataframe(metrics_df, use_container_width=True)

        st.subheader("📈 歷史價格走勢圖")
        fig = px.line(
            item_df, x='date', y='price', color='supermarket',
            title=f"{selected_item} 在各大超市的價格走勢",
            labels={'date': '日期', 'price': '價格 (HKD)', 'supermarket': '超市'},
            markers=True
        )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)


# ==========================================
# 頁面 2：同類別貨品價格比較 (Cat1 / Category / Brand)
# ==========================================
elif page == "同類別貨品價格比較 (Cat1 / Category)":
    st.sidebar.header("📊 類別比較條件")

    # 1. 選擇主類別 cat1
    cat1_list = sorted(df['cat1'].dropna().unique().tolist())
    selected_cat1 = st.sidebar.selectbox("1. 選擇主類別 (Cat1)", options=cat1_list)

    # 2. 根據 Cat1 篩選子類別 Category
    df_cat1 = df[df['cat1'] == selected_cat1]
    category_list = sorted(df_cat1['category'].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox("2. 選擇子類別 (Category)", options=["全部子類別"] + category_list)

    # 套用 Category 篩選
    if selected_category == "全部子類別":
        df_cat = df_cat1
        cat_tag = f"{selected_cat1}"
    else:
        df_cat = df_cat1[df_cat1['category'] == selected_category]
        cat_tag = f"{selected_cat1} ➔ {selected_category}"

    # 3. 新增功能：根據 Cat1/Category 連動篩選 Brand
    brand_list = sorted(df_cat['brand'].dropna().unique().tolist())
    selected_brands = st.sidebar.multiselect("3. 選擇品牌 (可多選，留空為全部)", options=brand_list, default=[])

    # 最終類別數據集
    if selected_brands:
        cat_df = df_cat[df_cat['brand'].isin(selected_brands)]
        title_tag = f"{cat_tag} (指定品牌)"
    else:
        cat_df = df_cat
        title_tag = cat_tag

    st.subheader(f"🏷️ 品類數據總覽：【{title_tag}】")

    if cat_df.empty:
        st.warning("⚠️ 該篩選條件下暫無數據，請調整品牌或類別！")
        st.stop()

    # 1. 關鍵指標卡片 (KPI Summary)
    latest_date = cat_df['date'].max()
    latest_cat_df = cat_df[cat_df['date'] == latest_date]

    # 計算 52 周最高/最低
    one_year_ago = latest_date - timedelta(days=365)
    df_52w = cat_df[cat_df['date'] >= one_year_ago]

    max_52w = df_52w['price'].max()
    min_52w = df_52w['price'].min()

    most_expensive_item = latest_cat_df.loc[latest_cat_df['price'].idxmax()] if not latest_cat_df.empty else None
    cheapest_item = latest_cat_df.loc[latest_cat_df['price'].idxmin()] if not latest_cat_df.empty else None

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏆 最便宜貨品 (最新)", 
                  f"${cheapest_item['price']:.2f}" if cheapest_item is not None else "N/A", 
                  f"{cheapest_item['item_name']} ({cheapest_item['supermarket']})" if cheapest_item is not None else "")
    with col2:
        st.metric("💎 最昂貴貨品 (最新)", 
                  f"${most_expensive_item['price']:.2f}" if most_expensive_item is not None else "N/A", 
                  f"{most_expensive_item['item_name']} ({most_expensive_item['supermarket']})" if most_expensive_item is not None else "")
    with col3:
        st.metric("📈 品類 52 周最高價", f"${max_52w:.2f}" if pd.notna(max_52w) else "N/A")
    with col4:
        st.metric("📉 品類 52 周最低價", f"${min_52w:.2f}" if pd.notna(min_52w) else "N/A")

    st.markdown("---")

    # 2. 最新價格排行榜
    st.subheader("📋 同類別貨品現時價格排行榜 (最便宜 ➡️ 最貴)")
    summary_table = latest_cat_df.groupby(['item_name', 'brand', 'supermarket'])['price'].min().reset_index()
    summary_table = summary_table.sort_values(by='price', ascending=True)
    summary_table.columns = ['貨品名稱', '品牌', '超市', '最新價格 (HKD)']
    st.dataframe(summary_table, use_container_width=True)

    # 3. 歷史走勢折線圖比較
    st.subheader("📈 同類別貨品歷史價格走勢比較")
    top_items = cat_df['item_name'].unique().tolist()[:5]
    selected_compare_items = st.multiselect("選擇要加入折線圖比較的貨品 (可多選):", options=cat_df['item_name'].unique().tolist(), default=top_items)

    if selected_compare_items:
        compare_df = cat_df[cat_df['item_name'].isin(selected_compare_items)]
        fig_cat = px.line(
            compare_df, 
            x='date', 
            y='price', 
            color='item_name',
            line_dash='supermarket',
            title=f"{title_tag} 各貨品價格走勢橫向比較",
            labels={'date': '日期', 'price': '價格 (HKD)', 'item_name': '貨品名稱', 'supermarket': '超市'},
            markers=True
        )
        fig_cat.update_layout(hovermode="x unified")
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("請在上方選擇至少一個貨品以顯示折線圖比較！")
