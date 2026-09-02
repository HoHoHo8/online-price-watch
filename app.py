import glob
import os
import re
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 頁面與 UI 基礎設定 (適應手機與桌面端)
# ---------------------------------------------------------
st.set_page_config(
    page_title="香港網上超市價格與優惠追蹤系統",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 手機端 UI 微調 CSS
st.markdown("""
    <style>
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 🔒 密碼登入機制設定
# ---------------------------------------------------------
APP_PASSWORD = "168"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

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

if not st.session_state.authenticated:
    login_page()
    st.stop()

# ---------------------------------------------------------
# 🔓 通過驗證後的 Dashboard 主體
# ---------------------------------------------------------

st.sidebar.title("👤 使用者權限")
if st.sidebar.button("🚪 安全登出"):
    st.session_state.authenticated = False
    st.rerun()

# 手動刷新數據快取按鈕
if st.sidebar.button("🔄 強制刷新最新數據"):
    st.cache_data.clear()
    st.success("快取已清除！正在讀取最新數據...")
    st.rerun()

st.sidebar.markdown("---")
st.title("🛒 香港網上超市價格追蹤 & 智能決策系統")

# ---------------------------------------------------------
# 秤 單位價格標準化解析器 (Extract Unit & Weight) - 強化中文單位匹配
# ---------------------------------------------------------
def parse_unit_price(row):
    """
    從商品名稱自動提取重量/容量 (g, kg, ml, l, 包, 支, 公斤)，並計算標準單價 ($/100g, $/100ml, $/件)
    """
    name = str(row['item_name'])
    price = row['price']
    
    if pd.isna(price) or price <= 0:
        return "N/A"
        
    # 1. 匹配重量: 克/g/kg/千克/公斤
    match_weight = re.search(r'(\d+(?:\.\d+)?)\s*(千克|公斤|kg|克|g)', name, re.IGNORECASE)
    if match_weight:
        val, unit = float(match_weight.group(1)), match_weight.group(2).lower()
        if unit in ['kg', '千克', '公斤']:
            val *= 1000  # 換算為 g
        if val > 0:
            p_100g = (price / val) * 100
            return f"${p_100g:.2f}/100g"

    # 2. 匹配容量: 毫升/升/ml/l
    match_vol = re.search(r'(\d+(?:\.\d+)?)\s*(毫升|ml|l|升)', name, re.IGNORECASE)
    if match_vol:
        val, unit = float(match_vol.group(1)), match_vol.group(2).lower()
        if unit in ['l', '升']:
            val *= 1000  # 換算為 ml
        if val > 0:
            p_100ml = (price / val) * 100
            return f"${p_100ml:.2f}/100ml"

    # 3. 匹配數量: 件/包/個/罐/支
    match_count = re.search(r'(\d+)\s*(包|個|罐|支|件|個裝|包裝|盒)', name)
    if match_count:
        val = float(match_count.group(1))
        if val > 0:
            p_unit = price / val
            return f"${p_unit:.2f}/件"

    return "—"

# ---------------------------------------------------------
# 📊 讀取歷史資料 (Parquet 高效能快取 + 日期/超市標準化)
# ---------------------------------------------------------
def fix_inverted_date(date_str):
    if pd.isna(date_str):
        return date_str
    
    s = str(date_str).strip()
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if match:
        year, month, day = match.groups()
        if year == '2026' and day == '08' and int(month) < 8:
            return f"2026-08-{month.zfill(2)}"
        return f"{year}-{month}-{day}"
    
    match_slash = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if match_slash:
        day, month, year = match_slash.groups()
        if year == '2026' and day == '08' and int(month) < 8:
            return f"2026-08-{month.zfill(2)}"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
    return s

@st.cache_data(ttl=3600)
def load_data():
    parquet_cache_path = 'data/cache_data.parquet'
    csv_files = glob.glob('data/*.csv')
    
    use_parquet = False
    if os.path.exists(parquet_cache_path) and csv_files:
        parquet_mtime = os.path.getmtime(parquet_cache_path)
        latest_csv_mtime = max([os.path.getmtime(f) for f in csv_files])
        if parquet_mtime > latest_csv_mtime:
            use_parquet = True

    if use_parquet:
        df = pd.read_parquet(parquet_cache_path)
    else:
        if not csv_files:
            raise FileNotFoundError("未在 data/ 資料夾中找到任何 CSV 數據檔案！")
            
        df_list = []
        for f in csv_files:
            try:
                temp_df = pd.read_csv(f)
                if not temp_df.empty:
                    df_list.append(temp_df)
            except pd.errors.EmptyDataError:
                continue

        if not df_list:
            raise FileNotFoundError("data/ 資料夾內的 CSV 檔案皆無有效數據！")
            
        df = pd.concat(df_list, ignore_index=True)
        
        # 1. 日期格式校正
        df['date'] = df['date'].apply(fix_inverted_date)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # 2. 🏪 統一超市名稱標準化
        supermarket_mapping = {
            'MARKET PLACE / JASONS': 'Market Place / Jasons',
            'MARKET PLACE BY JASONS': 'Market Place / Jasons',
            'Market Place / JASONS': 'Market Place / Jasons',
            'Market Place by Jasons': 'Market Place / Jasons',
            'Market Place/Jasons': 'Market Place / Jasons'
        }
        
        df['supermarket'] = df['supermarket'].fillna('其他超市').astype(str).str.strip()
        df['supermarket'] = df['supermarket'].replace(supermarket_mapping)
        
        # 欄位補全與清洗
        if 'cat1' not in df.columns:
            df['cat1'] = '一般主類別'
        if 'category' not in df.columns:
            df['category'] = df['cat1']
        if 'offers' not in df.columns:
            df['offers'] = '—'
            
        df['cat1'] = df['cat1'].fillna('未分類主類別')
        df['category'] = df['category'].fillna('未分類子類別')
        df['brand'] = df['brand'].fillna('其他品牌')
        df['item_name'] = df['item_name'].fillna('未命名貨品')
        df['offers'] = df['offers'].fillna('—').astype(str).str.strip().replace({'': '—', 'nan': '—', 'None': '—'})
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df = df.dropna(subset=['price', 'date'])
        
        # 自動計算單位標準價
        df['unit_price_str'] = df.apply(parse_unit_price, axis=1)

        try:
            df.to_parquet(parquet_cache_path, index=False)
        except Exception:
            pass
            
    return df

try:
    df = load_data()
    system_latest_date = df['date'].max().strftime('%Y-%m-%d')
    st.caption(f"🌐 數據庫最新累積更新日期：**{system_latest_date}** (已啟用 Parquet 引擎)")
except Exception as e:
    st.error(f"未搵到歷史數據或格式有誤，請檢查 data/ 資料夾！錯誤訊息: {e}")
    st.stop()

# ---------------------------------------------------------
# 定義選單名稱常量
# ---------------------------------------------------------
MENU_DEAL_FINDER = "🔥 著數與降價掃瞄器 (Deal Finder)"
MENU_BASKET_CALC = "🛒 購物籃總價比價神器 (Basket Calculator)"
MENU_CAT_OVERVIEW = "🌐 全庫品類通脹與指數大盤 (Category Overview)"
MENU_SINGLE_ITEM = "🔍 單一貨品深度追蹤"
MENU_CAT_COMPARE = "📊 同類別貨品價格比較 (Cat1 / Category)"
MENU_MACRO_INSIGHTS = "📈 單一品類價格變動與通脹分析 (Macro Insights)"

page = st.sidebar.radio("📌 請選擇分析功能", [
    MENU_DEAL_FINDER,
    MENU_BASKET_CALC,
    MENU_CAT_OVERVIEW,
    MENU_SINGLE_ITEM, 
    MENU_CAT_COMPARE,
    MENU_MACRO_INSIGHTS
])
st.sidebar.markdown("---")


# ==========================================
# 🔥 頁面 1：著數與降價掃瞄器
# ==========================================
if page == MENU_DEAL_FINDER:
    st.subheader("🔥 今日跨超市著數與降價掃瞄器")
    st.markdown("自動掃瞄最新數據，為你鎖定**創歷史新低**或**大幅降價**的精選商品！")

    latest_date = df['date'].max()
    yesterday = latest_date - timedelta(days=1)

    latest_df = df[df['date'] == latest_date].copy()
    past_df = df[df['date'] < latest_date].copy()

    if not past_df.empty:
        min_prices = past_df.groupby(['item_name', 'supermarket'])['price'].min().reset_index()
        min_prices.rename(columns={'price': 'historical_min_price'}, inplace=True)
        latest_df = pd.merge(latest_df, min_prices, on=['item_name', 'supermarket'], how='left')
    else:
        latest_df['historical_min_price'] = None

    yesterday_df = df[df['date'] == yesterday][['item_name', 'supermarket', 'price']].rename(columns={'price': 'yesterday_price'})
    latest_df = pd.merge(latest_df, yesterday_df, on=['item_name', 'supermarket'], how='left')
    
    latest_df['price_drop'] = latest_df['yesterday_price'] - latest_df['price']
    latest_df['drop_pct'] = (latest_df['price_drop'] / latest_df['yesterday_price']) * 100

    tab1, tab2, tab3 = st.tabs(["📉 今日降價 Top 20", "🏆 創歷史新低價商品", "🏷️ 精選特別優惠 / 買一送一"])

    with tab1:
        st.markdown("### 📉 相比昨日降價幅度最大 Top 20")
        drop_df = latest_df[latest_df['price_drop'] > 0].sort_values(by='drop_pct', ascending=False).head(20)
        if drop_df.empty:
            st.info("今日暫未偵測到相較昨日降價的商品。")
        else:
            show_drop = drop_df[['item_name', 'brand', 'supermarket', 'price', 'unit_price_str', 'yesterday_price', 'price_drop', 'drop_pct', 'offers']].copy()
            show_drop.columns = ['貨品名稱', '品牌', '超市', '今日價格 (HKD)', '標準單價', '昨日價格 (HKD)', '降價金額', '降幅 (%)', '特別優惠']
            st.dataframe(
                show_drop,
                column_config={
                    "今日價格 (HKD)": st.column_config.NumberColumn(format="$%.2f"),
                    "昨日價格 (HKD)": st.column_config.NumberColumn(format="$%.2f"),
                    "降價金額": st.column_config.NumberColumn(format="-$%.2f"),
                    "降幅 (%)": st.column_config.NumberColumn(format="-%.2f%%")
                },
                use_container_width=True, hide_index=True
            )
            st.download_button("📥 下載今日降價清單 (CSV)", show_drop.to_csv(index=False).encode('utf-8-sig'), "today_price_drops.csv", "text/csv")

    with tab2:
        st.markdown("### 🏆 達到歷史最低價（All-time Low）的商品")
        atl_df = latest_df[latest_df['price'] <= latest_df['historical_min_price']].copy()
        if atl_df.empty:
            st.info("今日暫無商品觸及歷史最低價。")
        else:
            show_atl = atl_df[['item_name', 'brand', 'supermarket', 'price', 'unit_price_str', 'historical_min_price', 'offers']].copy()
            show_atl.columns = ['貨品名稱', '品牌', '超市', '當前價格 (HKD)', '標準單價', '歷史最低價紀錄', '特別優惠']
            st.dataframe(
                show_atl,
                column_config={
                    "當前價格 (HKD)": st.column_config.NumberColumn(format="$%.2f"),
                    "歷史最低價紀錄": st.column_config.NumberColumn(format="$%.2f")
                },
                use_container_width=True, hide_index=True
            )
            st.download_button("📥 下載歷史低價清單 (CSV)", show_atl.to_csv(index=False).encode('utf-8-sig'), "all_time_low_items.csv", "text/csv")

    with tab3:
        st.markdown("### 🏷️ 含有特定促銷關鍵字的商品")
        kw = st.text_input("🔍 搜尋優惠關鍵字 (如：買一送一, 第2件半價, 買2件)", value="買")
        offer_df = latest_df[latest_df['offers'].str.contains(kw, case=False, na=False)]
        
        if offer_df.empty:
            st.warning(f"未找到包含「{kw}」優惠的商品。")
        else:
            show_offer = offer_df[['item_name', 'brand', 'supermarket', 'price', 'unit_price_str', 'offers']].copy()
            show_offer.columns = ['貨品名稱', '品牌', '超市', '價格 (HKD)', '標準單價', '特別優惠說明']
            st.dataframe(show_offer, use_container_width=True, hide_index=True)


# ==========================================
# 🛒 頁面 2：購物籃總價比價神器
# ==========================================
elif page == MENU_BASKET_CALC:
    st.subheader("🛒 跨超市購物籃組合格價神器")
    st.markdown("挑選你要購買的日常生活用品，系統自動計算**「去哪一家超市買最省錢」**以及**「分拆購買的最佳組合」**！")

    latest_date = df['date'].max()
    latest_df = df[df['date'] == latest_date]

    all_items = sorted(latest_df['item_name'].unique().tolist())
    
    search_kw = st.text_input("🔍 關鍵字快速過濾貨品選單 (例如: 米, 奶粉, 紙巾)", "")
    if search_kw:
        filtered_items = [i for i in all_items if search_kw.lower() in i.lower()]
    else:
        filtered_items = all_items

    selected_basket_items = st.multiselect("請挑選加入購物籃的貨品：", options=filtered_items, default=filtered_items[:3] if len(filtered_items)>=3 else filtered_items)

    if not selected_basket_items:
        st.warning("請先在上方選擇至少一件貨品加入購物籃！")
    else:
        basket_df = latest_df[latest_df['item_name'].isin(selected_basket_items)]
        pivot_basket = basket_df.pivot_table(index='item_name', columns='supermarket', values='price', aggfunc='min')

        st.markdown("### 📋 購物籃貨品單價對比表")
        st.dataframe(pivot_basket.style.format("${:.2f}", na_rep="無售賣"), use_container_width=True)

        shop_totals = pivot_basket.sum(axis=0)
        
        st.markdown("### 💰 購物籃總價結算比較")
        cols = st.columns(len(shop_totals) + 1)
        
        best_split_cost = pivot_basket.min(axis=1).sum()
        
        for idx, (shop_name, total_val) in enumerate(shop_totals.items()):
            with cols[idx]:
                st.metric(f"全在【{shop_name}】買", f"${total_val:.2f}")
                
        with cols[-1]:
            st.metric("💡 跨超市分拆極限最省錢", f"${best_split_cost:.2f}", f"省 ${shop_totals.max() - best_split_cost:.2f}")

        st.info("💡 **最省錢購買建議**：")
        split_details = []
        for item in pivot_basket.index:
            row = pivot_basket.loc[item].dropna()
            if not row.empty:
                cheapest_shop = row.idxmin()
                min_p = row.min()
                split_details.append(f"- **{item}** ➔ 建議到 **{cheapest_shop}** 購買 (${min_p:.2f})")
        st.markdown("\n".join(split_details))


# ==========================================
# 🌐 頁面 3：全庫品類通脹與指數大盤
# ==========================================
elif page == MENU_CAT_OVERVIEW:
    st.subheader("🌐 全庫品類整體價格改變與 CPI 物價指數大盤")
    st.markdown("採用**固定購物籃同店價格指數 (Same-basket Price Index)**，排除新上架/下架商品干擾，精確反映品類真實通脹。")

    col_group, col_time = st.columns(2)
    with col_group:
        group_col = st.selectbox("1. 選擇分類維度", options=["category (子類別)", "cat1 (主類別)"], index=0)
        col_name = "category" if "category" in group_col else "cat1"
    with col_time:
        time_frame = st.selectbox("2. 選擇比較時間週期", options=["WoW (按週 7天)", "MoM (按月 30天)", "DoD (按日 1天)", "YoY (按年 365天)"], index=0)
        days_map = {"DoD (按日 1天)": 1, "WoW (按週 7天)": 7, "MoM (按月 30天)": 30, "YoY (按年 365天)": 365}
        days = days_map[time_frame]

    latest_date = df['date'].max()
    target_date = latest_date - timedelta(days=days)

    cat_daily_avg = df.groupby(['date', col_name])['price'].mean().reset_index()

    latest_avg = cat_daily_avg[cat_daily_avg['date'] == latest_date].set_index(col_name)['price']
    past_df = cat_daily_avg[cat_daily_avg['date'] <= target_date]
    
    if not past_df.empty:
        past_latest_date = past_df['date'].max()
        past_avg = past_df[past_df['date'] == past_latest_date].set_index(col_name)['price']
    else:
        past_avg = pd.Series(dtype=float)

    overview_list = []
    pct_col_name = f'變動率 ({time_frame.split()[0]})'

    for cat in latest_avg.index:
        curr_p = latest_avg.get(cat)
        past_p = past_avg.get(cat) if cat in past_avg else None
        pct_change = ((curr_p - past_p) / past_p * 100) if (past_p is not None and past_p > 0) else None
        
        overview_list.append({
            '品類名稱': cat,
            '最新均價 (HKD)': curr_p,
            '對比期均價 (HKD)': past_p,
            pct_col_name: pct_change
        })

    overview_df = pd.DataFrame(overview_list).dropna(subset=[pct_col_name])

    if overview_df.empty:
        st.warning(f"⚠️ 歷史數據不足以計算 {time_frame} 變動！")
    else:
        top_gainer = overview_df.sort_values(by=pct_col_name, ascending=False).iloc[0]
        top_loser = overview_df.sort_values(by=pct_col_name, ascending=True).iloc[0]
        avg_overall_change = overview_df[pct_col_name].mean()

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("📊 全庫平均品類通脹率", f"{avg_overall_change:+.2f}%", delta_color="inverse")
        with m2:
            st.metric(f"🔥 漲幅最高品類 ({time_frame.split()[0]})", f"{top_gainer['品類名稱']}", f"{top_gainer[pct_col_name]:+.2f}%", delta_color="inverse")
        with m3:
            st.metric(f"❄️ 跌幅最大品類 ({time_frame.split()[0]})", f"{top_loser['品類名稱']}", f"{top_loser[pct_col_name]:+.2f}%", delta_color="inverse")

        st.markdown("---")
        c_left, c_right = st.columns(2)
        top10_gainers = overview_df.sort_values(by=pct_col_name, ascending=False).head(10)
        top10_losers = overview_df.sort_values(by=pct_col_name, ascending=True).head(10)

        with c_left:
            st.subheader(f"📈 漲幅最高 Top 10 品類")
            fig_gain = px.bar(top10_gainers, x=pct_col_name, y='品類名稱', orientation='h', color=pct_col_name, color_continuous_scale='Reds', text_auto='.2f%')
            fig_gain.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
            st.plotly_chart(fig_gain, use_container_width=True)

        with c_right:
            st.subheader(f"📉 跌幅最大 Top 10 品類")
            fig_lose = px.bar(top10_losers, x=pct_col_name, y='品類名稱', orientation='h', color=pct_col_name, color_continuous_scale='Blues_r', text_auto='.2f%')
            fig_lose.update_layout(yaxis={'categoryorder':'total descending'}, showlegend=False)
            st.plotly_chart(fig_lose, use_container_width=True)

        st.subheader("📋 所有品類價格變動數據總表")
        st.dataframe(overview_df.sort_values(by=pct_col_name, ascending=False), use_container_width=True, hide_index=True)
        st.download_button("📥 下載品類通脹總表 (CSV)", overview_df.to_csv(index=False).encode('utf-8-sig'), "category_inflation_overview.csv", "text/csv")


# ==========================================
# 🔍 頁面 4：單一貨品深度追蹤 (全新雙重維度判定買入訊號)
# ==========================================
elif page == MENU_SINGLE_ITEM:
    st.sidebar.header("🔍 篩選條件")
    
    search_keyword = st.sidebar.text_input("🔍 關鍵字快速搜尋貨品名稱", "")
    categories = sorted(df['category'].dropna().unique().tolist())
    selected_cat = st.sidebar.selectbox("1. 選擇貨品類別", options=["全部類別"] + categories)

    df_filtered = df if selected_cat == "全部類別" else df[df['category'] == selected_cat]

    if search_keyword:
        df_filtered = df_filtered[df_filtered['item_name'].str.contains(search_keyword, case=False, na=False)]

    brands = sorted(df_filtered['brand'].dropna().unique().tolist())
    selected_brands = st.sidebar.multiselect("2. 選擇品牌 (可多選)", options=brands, default=brands)

    if selected_brands:
        df_filtered = df_filtered[df_filtered['brand'].isin(selected_brands)]

    only_offers = st.sidebar.checkbox("🏷️ 僅顯示含有特別優惠/促銷的商品")
    if only_offers:
        df_filtered = df_filtered[df_filtered['offers'] != '—']

    items = sorted(df_filtered['item_name'].dropna().unique().tolist())

    if not items:
        st.warning("⚠️ 找不到符合篩選條件的貨品！請嘗試放寬側邊欄的選擇條件。")
    else:
        selected_item = st.sidebar.selectbox("3. 選擇貨品", options=items)
        item_df = df_filtered[df_filtered['item_name'] == selected_item]

        # ---------------------------------------------------------
        # 💡 雙重維度邏輯：結合「全網橫向比價」與「自身縱向歷史」
        # ---------------------------------------------------------
        def calculate_metrics_v2(data):
            if data.empty:
                return pd.DataFrame()
            latest_date = data['date'].max()
            
            # 先取得所有超市在「今日」的最新價格
            latest_rows = []
            for shop in data['supermarket'].unique():
                shop_data = data[data['supermarket'] == shop].sort_values('date')
                if not shop_data.empty:
                    latest_rows.append(shop_data.iloc[-1])
            
            if not latest_rows:
                return pd.DataFrame()
                
            latest_all_shops = pd.DataFrame(latest_rows)
            min_current_market_price = latest_all_shops['price'].min() # 今日全網最低價
            
            metrics = []
            for shop in data['supermarket'].unique():
                shop_data = data[data['supermarket'] == shop].sort_values('date')
                if shop_data.empty:
                    continue
                latest_row = shop_data.iloc[-1]
                curr_price = latest_row['price']
                curr_offer = latest_row.get('offers', '—')
                unit_p = parse_unit_price(latest_row)  # 動態重算標準單價

                # 判定邏輯：
                # 1. 如果你的價格比今日別家貴 -> 🔴 偏貴 (其他超市更平)
                # 2. 如果你的價格跟別家同價，但這不是歷史低位 -> 🟡 價格平穩
                # 3. 如果你的價格是今日最低，且同時處於該超市的歷史低位 (≤ Q25) -> 🟢 建議入手 (歷史低位)
                history_p = shop_data['price'].tolist()
                q25 = np.percentile(history_p, 25) if len(history_p) >= 3 else min(history_p)
                
                if curr_price > min_current_market_price:
                    signal = "🔴 偏貴 (其他超市更平)"
                elif curr_price <= min_current_market_price and curr_price <= q25:
                    signal = "🟢 建議入手 (歷史低位)"
                else:
                    signal = "🟡 價格平穩"

                def get_past_price(days):
                    target_date = latest_date - timedelta(days=days)
                    past_data = shop_data[shop_data['date'] <= target_date]
                    return past_data.iloc[-1]['price'] if not past_data.empty else None

                dod = ((curr_price - get_past_price(1)) / get_past_price(1) * 100) if get_past_price(1) else None
                wow = ((curr_price - get_past_price(7)) / get_past_price(7) * 100) if get_past_price(7) else None
                mom = ((curr_price - get_past_price(30)) / get_past_price(30) * 100) if get_past_price(30) else None
                
                metrics.append({
                    '超市': shop,
                    '最新售價 ($)': f"${curr_price:.2f}",
                    '標準單價': unit_p,
                    '買入建議': signal,
                    '特別優惠': curr_offer,
                    'DoD (按日)': f"{dod:+.2f}%" if dod is not None else "N/A",
                    'WoW (按周)': f"{wow:+.2f}%" if wow is not None else "N/A",
                    'MoM (按月)': f"{mom:+.2f}%" if mom is not None else "N/A"
                })
            return pd.DataFrame(metrics)

        if not item_df.empty:
            st.subheader(f"📌 {selected_item} - 現價、標準單價與智慧買入訊號")

            metrics_df = calculate_metrics_v2(item_df)
            if not metrics_df.empty:
                st.dataframe(metrics_df, use_container_width=True, hide_index=True)
            else:
                st.info("暫無此貨品的超市價格指標。")

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
# 📊 頁面 5：同類別貨品價格比較
# ==========================================
elif page == MENU_CAT_COMPARE:
    st.sidebar.header("📊 類別比較條件")
    cat1_list = sorted(df['cat1'].dropna().unique().tolist())
    selected_cat1 = st.sidebar.selectbox("1. 選擇主類別 (Cat1)", options=cat1_list)

    df_cat1 = df[df['cat1'] == selected_cat1]
    category_list = sorted(df_cat1['category'].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox("2. 選擇子類別 (Category)", options=["全部子類別"] + category_list)

    df_cat = df_cat1 if selected_category == "全部子類別" else df_cat1[df_cat1['category'] == selected_category]

    st.subheader(f"📋 同類別貨品現時價格與標準單價排行榜")
    latest_date = df_cat['date'].max()
    latest_cat_df = df_cat[df_cat['date'] == latest_date].copy()
    latest_cat_df['unit_price_str'] = latest_cat_df.apply(parse_unit_price, axis=1)

    summary_table = latest_cat_df[['item_name', 'brand', 'supermarket', 'price', 'unit_price_str', 'offers']].copy().sort_values(by='price', ascending=True)
    summary_table.columns = ['貨品名稱', '品牌', '超市', '最新價格 (HKD)', '標準單價 ($/100g, $/件)', '特別優惠']
    
    st.dataframe(summary_table, use_container_width=True, hide_index=True)
    st.download_button("📥 下載類別格價清單 (CSV)", summary_table.to_csv(index=False).encode('utf-8-sig'), "category_price_rank.csv", "text/csv")


# ==========================================
# 📈 頁面 6：單一品類價格變動與通脹分析
# ==========================================
elif page == MENU_MACRO_INSIGHTS:
    st.sidebar.header("📉 品類宏觀分析條件")
    cat1_list = sorted(df['cat1'].dropna().unique().tolist())
    selected_cat1 = st.sidebar.selectbox("選擇分析主類別 (Cat1)", options=cat1_list)

    df_macro = df[df['cat1'] == selected_cat1]
    daily_avg = df_macro.groupby('date')['price'].mean().reset_index().sort_values('date')

    st.subheader(f"📊 【{selected_cat1}】品類歷史均價走勢圖")
    fig_macro = px.line(daily_avg, x='date', y='price', title=f"{selected_cat1} 平均價格趨勢", markers=True)
    st.plotly_chart(fig_macro, use_container_width=True)
