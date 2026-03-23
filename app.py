# 导入所需库
import streamlit as st
import pandas as pd
from datetime import datetime
import random

# ====================== 页面基础设置 ======================
# 设置页面标题和布局
st.set_page_config(
    page_title="我的股票监控面板",
    page_icon="📈",
    layout="wide"
)
st.title("📈 我的股票监控面板")

# ====================== 核心配置 ======================
# 定义需要监控的股票列表（可自行修改）
STOCK_LIST = [
    {"代码": "600000", "名称": "浦发银行", "基准价": 11.7},
    {"代码": "000001", "名称": "平安银行", "基准价": 12.3},
    {"代码": "300059", "名称": "东方财富", "基准价": 16.7},
    {"代码": "601318", "名称": "中国平安", "基准价": 42.5},
    {"代码": "000858", "名称": "五粮液", "基准价": 148.2}
]

# 异动提醒阈值（涨跌幅超过±2%触发提醒）
ABNORMAL_THRESHOLD = 2.0

# ====================== 数据生成函数 ======================
@st.cache_data(ttl=60)  # 缓存60秒，1分钟自动刷新一次数据
def generate_simulated_stock_data(stock_list):
    """生成模拟真实波动的股票数据"""
    data = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for stock in stock_list:
        # 模拟±1.5%以内的随机价格波动（更贴近真实行情）
        price_fluctuation = random.uniform(-0.015, 0.015)
        current_price = round(stock["基准价"] * (1 + price_fluctuation), 2)
        
        # 计算涨跌幅（百分比）
        change_pct = round((current_price - stock["基准价"]) / stock["基准价"] * 100, 2)
        
        # 模拟成交量（200-800万手区间）
        volume = round(random.randint(200, 800), 2)
        
        # 组装单只股票数据
        data.append({
            "股票代码": stock["代码"],
            "股票名称": stock["名称"],
            "当前价格(元)": current_price,
            "涨跌幅(%)": change_pct,
            "成交量(万手)": volume,
            "更新时间": current_time
        })
    
    # 转换为DataFrame，方便展示
    df = pd.DataFrame(data)
    return df

# ====================== 数据展示 ======================
# 1. 实时股票数据模块
st.subheader("🔍 实时股票数据")
stock_df = generate_simulated_stock_data(STOCK_LIST)

# 美化数据展示（涨跌幅标红/绿）
def highlight_change(val):
    """根据涨跌幅设置单元格颜色"""
    if val > 0:
        return 'background-color: #f0fff4; color: #0f5132'  # 涨：浅绿+深绿字
    elif val < 0:
        return 'background-color: #fff5f5; color: #842029'  # 跌：浅红+深红字
    else:
        return ''

# 应用样式并展示表格
styled_df = stock_df.style.applymap(
    highlight_change,
    subset=["涨跌幅(%)"]
)
st.dataframe(styled_df, use_container_width=True, hide_index=True)

# 2. 异动提醒模块
st.subheader("⚠️ 异动提醒")
# 筛选出涨跌幅超过阈值的股票
abnormal_stocks = stock_df[abs(stock_df["涨跌幅(%)"]) > ABNORMAL_THRESHOLD]

if abnormal_stocks.empty:
    st.success("✅ 暂无异常波动股票，行情平稳")
else:
    st.warning(f"🔴 发现 {len(abnormal_stocks)} 只股票波动异常（涨跌幅超过±{ABNORMAL_THRESHOLD}%）：")
    st.dataframe(
        abnormal_stocks.style.applymap(highlight_change, subset=["涨跌幅(%)"]),
        use_container_width=True,
        hide_index=True
    )

# ====================== 底部信息 ======================
st.divider()
st.caption(f"📅 最后更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ⚠️ 注：当前为模拟真实波动数据，仅供演示")
