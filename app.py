import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# ================= 0. 全局配置 =================
st.set_page_config(page_title="A股深度复盘报告", layout="wide")

# 获取绝对路径
current_folder = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_folder, 'market_sentiment_indices.csv')

# 颜色映射
COLOR_MAP = {
    '<-7%': '#008000', '-7~-3%': '#00B300', '-3~-1%': '#66CC66', '-1~0%': '#C3E6C3',
    '0~1%': '#FFD9D9', '1~3%': '#FF9999', '3~7%': '#FF4D4D', '>7%': '#FF0000'
}
ORDER_LIST = ['>7%', '3~7%', '1~3%', '0~1%', '-1~0%', '-3~-1%', '-7~-3%', '<-7%']

# ================= 1. 数据加载 =================
@st.cache_data
def load_data():
    if not os.path.exists(file_path):
        return None
    try:
        df = pd.read_csv(file_path)
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['date_str'] = df['date'].astype(str)
        # 预先处理好分类顺序
        df['group'] = pd.Categorical(df['group'], categories=ORDER_LIST, ordered=True)
        return df
    except Exception:
        return None

raw_df = load_data() # raw_df 是全量数据，包含所有历史数据

# ================= 2. 侧边栏 (只控制趋势图) =================
st.title("📊 A股全市场复盘 (独立交互版)")

if raw_df is None:
    st.error(f"❌ 数据文件未找到: {file_path}")
    st.stop()

with st.sidebar:
    st.header("⏳ 趋势图时间范围")
    st.caption("注意：此筛选仅影响 Part 1 和 Part 2 的趋势图。Part 3 单日统计可自由查看任意历史日期。")
    
    min_date = raw_df['date'].min()
    max_date = raw_df['date'].max()
    
    start_date = st.date_input("开始日期", min_date, min_value=min_date, max_value=max_date)
    end_date = st.date_input("结束日期", max_date, min_value=min_date, max_value=max_date)

# 🌟 关键修改：生成一个专门用于趋势分析的 DataFrame
# trend_df 受侧边栏控制
mask = (raw_df['date'] >= start_date) & (raw_df['date'] <= end_date)
trend_df = raw_df[mask].copy()

# ================= 3. 核心计算与可视化 =================

# --- Part 1: 历史趋势 (使用 trend_df) ---
st.subheader("1. 全市场涨跌分布历史趋势")

# 数据准备
daily_counts = trend_df.groupby(['date_str', 'group'], observed=False).size().reset_index(name='count')
daily_counts = daily_counts.sort_values(['date_str', 'group']) # 排序

# 绘图
fig_main = px.bar(
    daily_counts, 
    x='date_str', y='count', color='group',
    barmode='group', # 并排分组
    color_discrete_map=COLOR_MAP, 
    category_orders={'group': ORDER_LIST}
)
fig_main.update_layout(
    height=450, bargap=0.15, bargroupgap=0.05,
    xaxis=dict(title="", type='category', tickangle=-45),
    yaxis=dict(title="家数"), title="全A股区间分布趋势"
)
st.plotly_chart(fig_main, use_container_width=True)

# --- Part 2: 逻辑验证 (使用 trend_df) ---
st.subheader("2. 市场内生逻辑验证 (Logic Verification)")

# 计算指标
daily_metrics = trend_df.groupby('date_str').apply(
    lambda x: pd.Series({
        'median_pct': x['pct_chg'].median(),
        'up': (x['pct_chg'] > 0).sum(),
        'down': (x['pct_chg'] < 0).sum()
    }), include_groups=False
).reset_index()

daily_metrics['net'] = daily_metrics['up'] - daily_metrics['down']
daily_metrics['cum_net'] = daily_metrics['net'].cumsum()
daily_metrics['median_color'] = daily_metrics['median_pct'].apply(lambda x: '#FF4D4D' if x > 0 else '#00B300')

col2_1, col2_2 = st.columns(2)

# 左图：中位数
with col2_1:
    fig_median = go.Figure()
    fig_median.add_trace(go.Bar(
        x=daily_metrics['date_str'], y=daily_metrics['median_pct'],
        marker_color=daily_metrics['median_color'], opacity=0.3, name='当日幅度'
    ))
    fig_median.add_trace(go.Scatter(
        x=daily_metrics['date_str'], y=daily_metrics['median_pct'],
        mode='lines+markers', line=dict(color='#333333', width=2), name='趋势'
    ))
    fig_median.update_layout(title="<b>A. 真实体温：涨跌幅中位数</b>", height=400, xaxis=dict(type='category', tickangle=-45))
    st.plotly_chart(fig_median, use_container_width=True)

# 右图：ADL
with col2_2:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=daily_metrics['date_str'], y=daily_metrics['cum_net'],
        mode='lines+markers', fill='tozeroy', line=dict(color='#4682B4', width=3), name='ADL'
    ))
    fig_trend.update_layout(title="<b>B. 趋势验证：全市场腾落指数 (ADL)</b>", height=400, xaxis=dict(type='category', tickangle=-45))
    st.plotly_chart(fig_trend, use_container_width=True)


# =======================================================
# --- Part 3: 单日详细分布 (完全独立！使用 raw_df) ---
# =======================================================
st.markdown("---")
st.subheader("3. 单日详细分布 (独立查询)")

c3_1, c3_2 = st.columns([1, 2])
with c3_1:
    # 🌟 关键修改：这里的日期列表来自 raw_df (全量)，而不是 trend_df (筛选后)
    available_dates = sorted(raw_df['date'].unique(), reverse=True)
    selected_date = st.selectbox("📅 选择日期 (不受侧边栏限制):", available_dates)

with c3_2:
    index_options = ['全A股 (All)', '上证指数', '深证成指', '创业板指', '科创50', '上证50', '沪深300', '中证500', '中证1000']
    selected_index = st.selectbox("🔍 选择统计范围:", index_options)

# 1. 筛选数据：先从【全量数据 raw_df】里找那天的数据
day_raw = raw_df[raw_df['date'] == selected_date]

# 2. 如果选了那天没有数据 (极少情况，但防报错)
if day_raw.empty:
    st.warning(f"⚠️ {selected_date} 当天没有交易数据。")
else:
    # 3. 指数筛选逻辑
    if selected_index != '全A股 (All)':
        # 确保列存在再筛选
        if selected_index in day_raw.columns:
            day_raw = day_raw[day_raw[selected_index] == True]
        else:
            st.warning("⚠️ 数据文件中缺少该指数成分信息，显示全A数据。")

    # 4. 统计与绘图
    day_counts_detail = day_raw['group'].value_counts().reindex(ORDER_LIST, fill_value=0).reset_index()
    day_counts_detail.columns = ['group', 'count']
    day_counts_detail['color_hex'] = day_counts_detail['group'].map(COLOR_MAP)

    total_up = (day_raw['pct_chg'] > 0).sum()
    total_down = (day_raw['pct_chg'] < 0).sum()
    limit_up_count = (day_raw['pct_chg'] > 9.8).sum()
    limit_down_count = (day_raw['pct_chg'] < -9.8).sum()

    day_counts_detail['hover_text'] = day_counts_detail.apply(lambda row: f"区间: {row['group']}<br>家数: {row['count']}", axis=1)

    fig_day = px.bar(day_counts_detail, x='group', y='count', text='count')
    fig_day.update_traces(
        marker_color=day_counts_detail['color_hex'],
        textposition='outside', textfont_weight='bold',
        width=0.6, hovertemplate='%{hover_text}<extra></extra>'
    )
    
    title_text = f"<b>{selected_date} - {selected_index} 分布</b>"
    fig_day.update_layout(
        title=dict(text=title_text, x=0.5), 
        xaxis_title="", yaxis_title="家数",
        yaxis=dict(range=[0, day_counts_detail['count'].max() * 1.25]),
        xaxis=dict(showgrid=False),
        height=500
    )
    st.plotly_chart(fig_day, use_container_width=True)

    # 5. 底部数据条
    st.markdown(
        f"""<div style='display: flex; justify-content: space-between; font-family: "Microsoft YaHei", sans-serif; font-weight: bold; font-size: 16px; padding: 10px 0;'>
            <span style='color: #FF3333;'>上涨 {total_up} 家，其中: 涨停 {limit_up_count} 家</span>
            <span style='color: #00CC00;'>下跌 {total_down} 家，其中: 跌停 {limit_down_count} 家</span>
        </div>""",
        unsafe_allow_html=True
    )
