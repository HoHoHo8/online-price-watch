import glob
import os
import re
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. 頁面設定
st.set_page_config(page_title="香港網上超市價格與優惠追蹤系統", layout="wide")

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
st.title("🛒 香港網上超市價格追蹤 & 趨勢分析")

# ---------------------------------------------------------
# 📊 讀取歷史資料 (自動校正日期與超市名稱)
# ---------------------------------------------------------
def fix_inverted_date(date_str):
    """
    將原本被誤寫為 2026-MM-08 (MM < 08) 的日期，修復回 2026-08-MM
    """
    if pd.isna(date_str):
        return date_str
    
    s = str(date_str).strip()
    
    # 正則匹配 YYYY-MM-DD
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if match:
        year, month, day = match.groups()
        if year == '2026' and day == '08' and int(month) < 8:
            return f"2026-08-{month.zfill(2)}"
        return f"{year}-{month}-{day}"
    
    # 正則匹配 DD/MM/YYYY
    match_slash = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if match_slash:
        day, month, year = match_slash.groups()
        if year == '2026' and day == '08' and int(month) < 8:
            return f"2026-08-{month.zfill(2)}"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
    return s

@st.cache_data(ttl=60)
def load_data():
    csv_files = glob.glob('data/*.csv')
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
    
    # 2. 🏪 統一超市名稱標準化 (解決消委會大小寫/命名不一問題)
    supermarket_mapping = {
        'MARKET PLACE / JASONS': 'Market Place / Jasons',
        'MARKET PLACE BY JASONS': 'Market Place / Jasons',
        'Market Place / JASONS': 'Market Place / Jasons',
        'Market Place by Jasons': 'Market Place / Jasons',
        'Market Place/Jasons': 'Market Place / Jasons',
        'Market Place / Jasons': 'Market Place / Jasons'
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
    
    return df.dropna(subset=['price', 'date'])

try:
    df = load_data()
    system_latest_date = df['date'].max().strftime('%Y-%m-%d')
    st.caption(f"🌐 數據庫最新累積更新日期：**{system_latest_date}**")
except Exception as e:
    st.error(f"未搵到歷史數據或格式有誤，請檢查 data/ 資料夾！錯誤訊息: {e}")
    st.stop()

# 側邊欄：分頁選單（新增「全庫品類通脹與漲跌大盤」）
page = st.sidebar.radio("📌 請選擇分析功能", [
    "全庫品類通脹與漲跌大盤 (Category Overview)",
    "單一貨品深度追蹤", 
    "同類別貨品價格比較 (Cat1 / Category)",
    "單一品類價格變動與通脹分析 (Macro Insights)"
])
st.sidebar.markdown("---")


# ==========================================
# 🆕 頁面 0：全庫品類通脹與漲跌大盤 (Category Overview)
# ==========================================
if page == "全庫品類通脹與漲跌大盤 (Category Overview)":
    st.subheader("🌐 全庫所有品類整體價格改變與通脹大盤")
    st.markdown("監控數據庫內所有品類（Category）的整體平均價格波動，快速找出通脹/降價最明顯的品類。")

    col_group, col_time = st.columns(2)
    with col_group:
        group_col = st.selectbox("1. 選擇分類維度", options=["category (子類別)", "cat1 (主類別)"], index=0)
        col_name = "category" if "category" in group_col else "cat1"
    with col_time:
        time_frame = st.selectbox("2. 選擇比較時間週期", options=["WoW (按週 7天)", "MoM (按月 30天)", "DoD (按日 1天)", "YoY (按年 365天)"], index=0)
        days_map = {"DoD (按日 1天)": 1, "WoW (按週 7天)": 7, "MoM (按月 30天)": 30, "YoY (按年 365天)": 365}
        days = days_map[time_frame]

    # 計算全品類均價變動
    latest_date = df['date'].max()
    target_date = latest_date - timedelta(days=days)

    # 每天每個類別的平均單價
    cat_daily_avg = df.groupby(['date', col_name])['price'].mean().reset_index()

    latest_avg = cat_daily_avg[cat_daily_avg['date'] == latest_date].set_index(col_name)['price']
    
    # 尋找目標對比日期的均價
    past_df = cat_daily_avg[cat_daily_avg['date'] <= target_date]
    if not past_df.empty:
        past_latest_date = past_df['date'].max()
        past_avg = past_df[past_df['date'] == past_latest_date].set_index(col_name)['price']
    else:
        past_avg = pd.Series()

    overview_list = []
    for cat in latest_avg.index:
        curr_p = latest_avg.get(cat)
        past_p = past_avg.get(cat) if cat in past_avg else None
        
        pct_change = ((curr_p - past_p) / past_p * 100) if (past_p and past_p > 0) else None
        
        overview_list.append({
            '品類名稱': cat,
            '最新均價 (HKD)': curr_p,
            '對比期均價 (HKD)': past_p,
            f'變動率 ({time_frame.split()[0]})': pct_change
        })

    overview_df = pd.DataFrame(overview_list)
    overview_df = overview_df.dropna(subset=[f'变動率 ({time_frame.split()[0]})' if f'变動率 ({time_frame.split()[0]})' in overview_df else f'變動率 ({time_frame.split()[0]})'])

    pct_col_name = f'變動率 ({time_frame.split()[0]})'

    if overview_df.empty:
        st.warning(f"⚠️ 在 {target_date.strftime('%Y-%m-%d')} 之前暫無足夠歷史數據可供計算 {time_frame} 變動！")
    else:
        # 關鍵指標卡片
        top_gainer = overview_df.sort_values(by=pct_col_name, ascending=False).iloc[0]
        top_loser = overview_df.sort_values(by=pct_col_name, ascending=True).iloc[0]
        avg_overall_change = overview_df[pct_col_name].mean()

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("📊 全庫平均品類價格變動", f"{avg_overall_change:+.2f}%", delta_color="inverse")
        with m2:
            st.metric(f"🔥 漲幅最高品類 ({time_frame.split()[0]})", f"{top_gainer['品類名稱']}", f"{top_gainer[pct_col_name]:+.2f}%", delta_color="inverse")
        with m3:
            st.metric(f"❄️ 跌幅最大品類 ({time_frame.split()[0]})", f"{top_loser['品類名稱']}", f"{top_loser[pct_col_name]:+.2f}%", delta_color="inverse")

        st.markdown("---")

        # 兩欄展示排行榜
        c_left, c_right = st.columns(2)
        
        top10_gainers = overview_df.sort_values(by=pct_col_name, ascending=False).head(10)
        top10_losers = overview_df.sort_values(by=pct_col_name, ascending=True).head(10)

        with c_left:
            st.subheader(f"📈 漲幅最高 Top 10 品類 ({time_frame.split()[0]})")
            fig_gain = px.bar(
                top10_gainers, x=pct_col_name, y='品類名稱', orientation='h',
                color=pct_col_name, color_continuous_scale='Reds',
                text_auto='.2f%'
            )
            fig_gain.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
            st.plotly_chart(fig_gain, use_container_width=True)

        with c_right:
            st.subheader(f"📉 跌幅最大 Top 10 品類 ({time_frame.split()[0]})")
            fig_lose = px.bar(
                top10_losers, x=pct_col_name, y='品類名稱', orientation='h',
                color=pct_col_name, color_continuous_scale='Blues_r',
                text_auto='.2f%'
            )
            fig_lose.update_layout(yaxis={'categoryorder':'total descending'}, showlegend=False)
            st.plotly_chart(fig_lose, use_container_width=True)

        st.subheader("📋 所有品類價格變動完整數據表")
        st.dataframe(
            overview_df.sort_values(by=pct_col_name, ascending=False),
            column_config={
                "最新均價 (HKD)": st.column_config.NumberColumn(format="$%.2f"),
                "對比期均價 (HKD)": st.column_config.NumberColumn(format="$%.2f"),
                pct_col_name: st.column_config.NumberColumn(format="%+.2f%%")
            },
            use_container_width=True,
            hide_index=True
        )

        st.subheader("📈 自訂多品類平均價格趨勢對比")
        all_cats = sorted(overview_df['品類名稱'].tolist())
        default_cats = all_cats[:5] if len(all_cats) >= 5 else all_cats
        selected_cats_to_plot = st.multiselect("選擇要加入歷史走勢對比的品類：", options=all_cats, default=default_cats)

        if selected_cats_to_plot:
            plot_df = cat_daily_avg[cat_daily_avg[col_name].isin(selected_cats_to_plot)]
            fig_multi = px.line(
                plot_df, x='date', y='price', color=col_name,
                title="選定品類平均價格歷史走勢比較",
                labels={'date': '日期', 'price': '平均價格 (HKD)', col_name: '品類'},
                markers=True
            )
            fig_multi.update_layout(hovermode="x unified")
            st.plotly_chart(fig_multi, use_container_width=True)


# ==========================================
# 頁面 1：單一貨品深度追蹤
# ==========================================
elif page == "單一貨品深度追蹤":
    st.sidebar.header("🔍 篩選條件")
    categories = sorted(df['category'].dropna().unique().tolist())
    selected_cat = st.sidebar.selectbox("1. 選擇貨品類別", options=["全部類別"] + categories)

    df_filtered = df if selected_cat == "全部類別" else df[df['category'] == selected_cat]

    brands = sorted(df_filtered['brand'].dropna().unique().tolist())
    selected_brands = st.sidebar.multiselect("2. 選擇品牌 (可多選)", options=brands, default=brands)

    df_filtered = df_filtered[df_filtered['brand'].isin(selected_brands)] if selected_brands else df_filtered

    # 🏷️ 優惠篩選器
    only_offers = st.sidebar.checkbox("🏷️ 僅顯示含有特別優惠/促銷的商品")
    if only_offers:
        df_filtered = df_filtered[df_filtered['offers'] != '—']

    items = sorted(df_filtered['item_name'].dropna().unique().tolist())

    if not items:
        st.warning("⚠️ 找不到符合條件的貨品，請重新勾選品牌或類別！")
        st.stop()

    selected_item = st.sidebar.selectbox("3. 選擇貨品", options=items)
    item_df = df_filtered[df_filtered['item_name'] == selected_item]

    def calculate_metrics(data):
        if data.empty:
            return pd.DataFrame()
        latest_date = data['date'].max()
        metrics = []
        for shop in data['supermarket'].unique():
            shop_data = data[data['supermarket'] == shop].sort_values('date')
            if shop_data.empty:
                continue
            latest_row = shop_data.iloc[-1]
            curr_price = latest_row['price']
            curr_offer = latest_row.get('offers', '—')
            
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
                '特別優惠': curr_offer,
                'DoD (按日)': f"{dod:+.2f}%" if dod is not None else "N/A",
                'WoW (按周)': f"{wow:+.2f}%" if wow is not None else "N/A",
                'MoM (按月)': f"{mom:+.2f}%" if mom is not None else "N/A",
                'YoY (按年)': f"{yoy:+.2f}%" if yoy is not None else "N/A"
            })
        return pd.DataFrame(metrics)

    if not item_df.empty:
        item_latest_date_str = item_df['date'].max().strftime('%Y-%m-%d')
        st.subheader(f"📌 {selected_item} - 現價、優惠及歷史變動 (截至 {item_latest_date_str})")
        
        if item_latest_date_str < system_latest_date:
            st.warning(f"⚠️ 注意：此貨品在最新日期 ({system_latest_date}) 暫無數據，下方顯示為該貨品的最後紀錄日期 ({item_latest_date_str})。")

        metrics_df = calculate_metrics(item_df)
        st.dataframe(
            metrics_df, 
            column_config={
                "特別優惠": st.column_config.TextColumn("特別優惠", help="超市當前促銷/折扣活動")
            },
            use_container_width=True,
            hide_index=True
        )

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
# 頁面 2：同類別貨品價格比較 (Cat1 / Category)
# ==========================================
elif page == "同類別貨品價格比較 (Cat1 / Category)":
    st.sidebar.header("📊 類別比較條件")

    cat1_list = sorted(df['cat1'].dropna().unique().tolist())
    selected_cat1 = st.sidebar.selectbox("1. 選擇主類別 (Cat1)", options=cat1_list)

    df_cat1 = df[df['cat1'] == selected_cat1]
    category_list = sorted(df_cat1['category'].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox("2. 選擇子類別 (Category)", options=["全部子類別"] + category_list)

    if selected_category == "全部子類別":
        df_cat = df_cat1
        cat_tag = f"{selected_cat1}"
    else:
        df_cat = df_cat1[df_cat1['category'] == selected_category]
        cat_tag = f"{selected_cat1} ➔ {selected_category}"

    brand_list = sorted(df_cat['brand'].dropna().unique().tolist())
    selected_brands = st.sidebar.multiselect("3. 選擇品牌 (可多選，留空為全部)", options=brand_list, default=[])

    if selected_brands:
        cat_df = df_cat[df_cat['brand'].isin(selected_brands)]
        title_tag = f"{cat_tag} (指定品牌)"
    else:
        cat_df = df_cat
        title_tag = cat_tag

    only_offers = st.sidebar.checkbox("🏷️ 僅顯示含有特別優惠的貨品")
    if only_offers:
        cat_df = cat_df[cat_df['offers'] != '—']

    st.subheader(f"🏷️ 品類數據總覽：【{title_tag}】")

    if cat_df.empty:
        st.warning("⚠️ 該篩選條件下暫無數據，請調整品牌或類別！")
        st.stop()

    latest_date = cat_df['date'].max()
    latest_cat_df = cat_df[cat_df['date'] == latest_date]

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

    st.subheader("📋 同類別貨品現時價格與優惠排行榜 (最便宜 ➡️ 最貴)")
    
    summary_table = latest_cat_df[['item_name', 'brand', 'supermarket', 'price', 'offers']].copy()
    summary_table = summary_table.sort_values(by='price', ascending=True)
    summary_table.columns = ['貨品名稱', '品牌', '超市', '最新價格 (HKD)', '特別優惠']
    
    st.dataframe(
        summary_table, 
        column_config={
            "最新價格 (HKD)": st.column_config.NumberColumn("最新價格 (HKD)", format="$%.2f"),
            "特別優惠": st.column_config.TextColumn("特別優惠", help="超市當前促銷/折扣活動")
        },
        use_container_width=True,
        hide_index=True
    )

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


# ==========================================
# 頁面 3：單一品類價格變動與通脹分析 (Macro Insights)
# ==========================================
elif page == "單一品類價格變動與通脹分析 (Macro Insights)":
    st.sidebar.header("📉 品類宏觀分析條件")

    cat1_list = sorted(df['cat1'].dropna().unique().tolist())
    selected_cat1 = st.sidebar.selectbox("選擇分析主類別 (Cat1)", options=cat1_list)

    df_macro = df[df['cat1'] == selected_cat1]
    cat2_list = sorted(df_macro['category'].dropna().unique().tolist())
    selected_cat2 = st.sidebar.selectbox("選擇分析子類別 (Category)", options=["全選子類別"] + cat2_list)

    if selected_cat2 != "全選子類別":
        df_macro = df_macro[df_macro['category'] == selected_cat2]
        macro_title = f"{selected_cat1} ➔ {selected_cat2}"
    else:
        macro_title = f"{selected_cat1} (全部)"

    st.subheader(f"📊 單一品類整體價格變動指數：【{macro_title}】")

    if df_macro.empty:
        st.warning("⚠️ 該類別暫無數據！")
        st.stop()

    daily_avg = df_macro.groupby('date')['price'].mean().reset_index().sort_values('date')
    latest_date = daily_avg['date'].max()
    latest_avg_price = daily_avg.iloc[-1]['price']

    def get_cat_past_avg(days):
        target_date = latest_date - timedelta(days=days)
        past_df = daily_avg[daily_avg['date'] <= target_date]
        return past_df.iloc[-1]['price'] if not past_df.empty else None

    avg_dod = ((latest_avg_price - get_cat_past_avg(1)) / get_cat_past_avg(1) * 100) if get_cat_past_avg(1) else None
    avg_wow = ((latest_avg_price - get_cat_past_avg(7)) / get_cat_past_avg(7) * 100) if get_cat_past_avg(7) else None
    avg_mom = ((latest_avg_price - get_cat_past_avg(30)) / get_cat_past_avg(30) * 100) if get_cat_past_avg(30) else None
    avg_yoy = ((latest_avg_price - get_cat_past_avg(365)) / get_cat_past_avg(365) * 100) if get_cat_past_avg(365) else None

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("📅 品類 DoD (按日變動)", 
                  f"{avg_dod:+.2f}%" if avg_dod is not None else "N/A",
                  delta_color="inverse")
    with k2:
        st.metric("🗓️ 品類 WoW (按周變動)", 
                  f"{avg_wow:+.2f}%" if avg_wow is not None else "N/A",
                  delta_color="inverse")
    with k3:
        st.metric("🗓️ 品類 MoM (按月通脹)", 
                  f"{avg_mom:+.2f}%" if avg_mom is not None else "N/A",
                  delta_color="inverse")
    with k4:
        st.metric("🎆 品類 YoY (按年通脹)", 
                  f"{avg_yoy:+.2f}%" if avg_yoy is not None else "N/A",
                  delta_color="inverse")

    st.markdown("---")

    st.subheader("📈 品類平均價格指數走勢圖 (按日/週/月累積)")
    fig_macro = px.line(
        daily_avg, x='date', y='price',
        title=f"{macro_title} 品類平均單價走勢",
        labels={'date': '日期', 'price': '平均價格 (HKD)'},
        markers=True
    )
    fig_macro.update_traces(line_color='#FF4B4B', line_width=3)
    fig_macro.update_layout(hovermode="x unified")
    st.plotly_chart(fig_macro, use_container_width=True)

    st.subheader("🏪 各大超市在該品類的均價走勢比較")
    shop_daily_avg = df_macro.groupby(['date', 'supermarket'])['price'].mean().reset_index()
    
    fig_shop_macro = px.line(
        shop_daily_avg, x='date', y='price', color='supermarket',
        title=f"各大超市在【{macro_title}】的平均售價差異與趨勢",
        labels={'date': '日期', 'price': '超市平均售價 (HKD)', 'supermarket': '超市'},
        markers=True
    )
    fig_shop_macro.update_layout(hovermode="x unified")
    st.plotly_chart(fig_shop_macro, use_container_width=True)
