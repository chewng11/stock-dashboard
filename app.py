import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ================= 0. 全局配置 =================
st.set_page_config(page_title="A股深度复盘报告", layout="wide")
DATA_FILE = 'market_sentiment_indices.csv'  # 记得改文件名！

# 颜色映射
COLOR_MAP = {
    '<-7%': '#008000', '-7~-3%': '#00B300', '-3~-1%': '#66CC66', '-1~0%': '#C3E6C3',
    '0~1%': '#FFD9D9', '1~3%': '#FF9999', '3~7%': '#FF4D4D', '>7%': '#FF0000'
}
ORDER_LIST = ['>7%', '3~7%', '1~3%', '0~1%', '-1~0%', '-3~-1%', '-7~-3%', '<-7%']

# ================= 1. 数据加载 =================
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['date_str'] = df['date'].astype(str)
        df['group'] = pd.Categorical(df['group'], categories=ORDER_LIST, ordered=True)
        return df
    except FileNotFoundError:
        return None

raw_df = load_data()

# ================= 2. 侧边栏 =================
st.title("📊 A股全市场复盘 (指数透视版)")

if raw_df is None:
    st.error(f"未找到数据文件 `{DATA_FILE}`。请运行新的聚宽脚本。")
    st.stop()

with st.sidebar:
    st.header("⏳ 时间范围")
    min_date = raw_df['date'].min()
    max_date = raw_df['date'].max()
    start_date = st.date_input("开始日期", min_date, min_value=min_date, max_value=max_date)
    end_date = st.date_input("结束日期", max_date, min_value=min_date, max_value=max_date)

# 基础过滤 (时间维度)
mask = (raw_df['date'] >= start_date) & (raw_df['date'] <= end_date)
filtered_raw = raw_df[mask].copy()

# ================= 3. 核心计算与可视化 =================

# --- Part 1: 历史趋势 (全市场) ---
# 1. 准备数据
daily_counts = filtered_raw.groupby(['date_str', 'group'], observed=False).size().reset_index(name='count')

# 2. 强制排序：确保 >7% 在最左边，<-7% 在最右边
daily_counts['group'] = pd.Categorical(daily_counts['group'], categories=ORDER_LIST, ordered=True)
daily_counts = daily_counts.sort_values(['date_str', 'group'])

st.subheader("1. 全市场涨跌分布历史趋势")

# 3. 绘图 (核心修改在这里)
fig_main = px.bar(
    daily_counts, 
    x='date_str', 
    y='count', 
    color='group',
    # 🌟 关键参数：让柱子并排站立，而不是堆叠
    barmode='group',  
    color_discrete_map=COLOR_MAP, 
    category_orders={'group': ORDER_LIST}
)

# 4. 样式美化
fig_main.update_layout(
    height=450, 
    xaxis=dict(
        title="", 
        type='category',
        tickangle=-45 
    ),
    yaxis=dict(title="家数"),
    title="全A股区间分布",
    # 调整柱子之间的间距，让它们紧凑一点，像你的截图那样
    bargap=0.15,      # 不同日期的间距
    bargroupgap=0.05  # 同一天内不同颜色柱子的间距
)

st.plotly_chart(fig_main, use_container_width=True)
# =======================================================
# --- Part 2: 逻辑验证 (测谎仪 + 指南针) ---
# =======================================================
st.subheader("2. 市场内生逻辑验证 (Logic Verification)")

# 1. 核心计算：同时算中位数和涨跌家数
daily_metrics = filtered_raw.groupby('date_str').apply(
    lambda x: pd.Series({
        'median_pct': x['pct_chg'].median(),       # <--- 找回了中位数！
        'up': (x['pct_chg'] > 0).sum(),
        'down': (x['pct_chg'] < 0).sum()
    }), include_groups=False
).reset_index()

# 2. 衍生计算
daily_metrics['net'] = daily_metrics['up'] - daily_metrics['down']
daily_metrics['cum_net'] = daily_metrics['net'].cumsum()
# 给中位数上色
daily_metrics['median_color'] = daily_metrics['median_pct'].apply(lambda x: '#FF4D4D' if x > 0 else '#00B300')

# 3. 双图布局
col2_1, col2_2 = st.columns(2)

# 左图：中位数 (测谎仪)
with col2_1:
    fig_median = go.Figure()
    # 背景柱 (幅度)
    fig_median.add_trace(go.Bar(
        x=daily_metrics['date_str'], y=daily_metrics['median_pct'],
        marker_color=daily_metrics['median_color'], opacity=0.3, name='当日幅度'
    ))
    # 趋势线
    fig_median.add_trace(go.Scatter(
        x=daily_metrics['date_str'], y=daily_metrics['median_pct'],
        mode='lines+markers+text',
        text=daily_metrics['median_pct'].round(2), textposition="top center",
        line=dict(color='#333333', width=2), name='中位数趋势'
    ))
    fig_median.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1)
    fig_median.update_layout(
        title="<b>A. 真实体温：涨跌幅中位数</b>",
        yaxis_title="涨跌幅 (%)", xaxis=dict(type='category', tickangle=-45),
        height=400, showlegend=False, margin=dict(l=20, r=20, t=60, b=20)
    )
    st.plotly_chart(fig_median, use_container_width=True)

# 右图：ADL (指南针)
with col2_2:
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=daily_metrics['date_str'], y=daily_metrics['cum_net'],
        mode='lines+markers', fill='tozeroy', 
        line=dict(color='#4682B4', width=3), name='ADL'
    ))
    fig_trend.update_layout(
        title="<b>B. 趋势验证：全市场腾落指数 (ADL)</b>",
        yaxis_title="累计净值", xaxis=dict(type='category', tickangle=-45),
        height=400, showlegend=False, margin=dict(l=20, r=20, t=60, b=20)
    )
    # 加个专业注解
    fig_trend.add_annotation(
        text="注: ADL背离是趋势反转的先行指标",
        xref="paper", yref="paper",
        x=0.5, y=1.1, showarrow=False,
        font=dict(size=10, color="gray")
    )
    st.plotly_chart(fig_trend, use_container_width=True)


# =======================================================
# --- Part 3: 单日详细分布 (支持指数筛选！) ---
# =======================================================
st.markdown("---")
st.subheader("3. 单日详细分布 (指数透视)")

# 1. 布局控件：日期选择 + 指数选择
c3_1, c3_2 = st.columns([1, 2])
with c3_1:
    available_dates = sorted(raw_df['date'].unique(), reverse=True)
    selected_date = st.selectbox("📅 选择日期:", available_dates)

with c3_2:
    # 定义指数选项列表
    index_options = ['全A股 (All)', '上证指数', '深证成指', '创业板指', '科创50', '上证50', '沪深300', '中证500', '中证1000']
    selected_index = st.selectbox("🔍 选择统计范围 (指数成分):", index_options)

# 2. 数据过滤逻辑
day_raw = filtered_raw[filtered_raw['date'] == selected_date]

if selected_index != '全A股 (All)':
    # 如果选了特定指数，就用布尔列进行筛选
    # 例如：df[df['沪深300'] == True]
    day_raw = day_raw[day_raw[selected_index] == True]

# 3. 统计分布
day_counts_detail = day_raw['group'].value_counts().reindex(ORDER_LIST, fill_value=0).reset_index()
day_counts_detail.columns = ['group', 'count']
day_counts_detail['color_hex'] = day_counts_detail['group'].map(COLOR_MAP)

# 统计涨跌停
total_up = (day_raw['pct_chg'] > 0).sum()
total_down = (day_raw['pct_chg'] < 0).sum()
limit_up_count = (day_raw['pct_chg'] > 9.8).sum()
limit_down_count = (day_raw['pct_chg'] < -9.8).sum()

# 4. 绘图
day_counts_detail['hover_text'] = day_counts_detail.apply(lambda row: f"区间: {row['group']}<br>家数: {row['count']}", axis=1)

fig_day = px.bar(
    day_counts_detail, x='group', y='count', text='count',
    # 不用 color 以免错位，后面 update_traces 手动上色
)

fig_day.update_traces(
    marker_color=day_counts_detail['color_hex'],
    textposition='outside', 
    textfont_size=14, textfont_weight='bold',
    marker_line_color='black', marker_line_width=0.5,
    hovertemplate='%{hover_text}<extra></extra>',
    width=0.6 
)

# 动态标题
fig_day.update_layout(
    title=dict(text=f"<b>{selected_date} - {selected_index} 涨跌分布</b>", x=0.5), 
    xaxis_title="", yaxis_title="家数", 
    yaxis=dict(range=[0, day_counts_detail['count'].max() * 1.25], showgrid=True, gridcolor='rgba(200,200,200,0.2)'), 
    xaxis=dict(showgrid=False, type='category', categoryorder='array', categoryarray=ORDER_LIST),
    showlegend=False, height=500, plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig_day, use_container_width=True)

# 5. 底部同花顺风格条 (极简版)
st.markdown(
    f"""<div style='display: flex; justify-content: space-between; font-family: "Microsoft YaHei", sans-serif; font-weight: bold; font-size: 16px; padding: 10px 0;'>
        <span style='color: #FF3333;'>上涨 {total_up} 家，其中: 涨停 {limit_up_count} 家</span>
        <span style='color: #00CC00;'>下跌 {total_down} 家，其中: 跌停 {limit_down_count} 家</span>
    </div>""",
    unsafe_allow_html=True
)

