# 导入所需库
import streamlit as st
import pandas as pd
from datetime import datetime
import akshare as ak

# ====================== 页面基础设置 ======================
st.set_page_config(
    page_title="我的股票监控面板",
    page_icon="📈",
    layout="wide"
)
st.title("📈 我的股票监控面板（真实A股数据）")

# ====================== 核心配置 ======================
# 定义需要监控的A股代码列表（可自行修改）
WATCH_STOCK_CODES = ["600000", "000001", "300059", "601318", "000858"]
# 异动提醒阈值（涨跌幅超过±2%触发）
ABNORMAL_THRESHOLD = 2.0

# ====================== 真实数据获取函数 ======================
@st.cache_data(ttl=60)  # 缓存60秒，避免频繁请求API
def get_real_a_stock_data(watch_codes):
    """从AkShare获取A股实时行情数据"""
    try:
        # 获取全市场A股实时行情（核心接口）
        df = ak.stock_zh_a_spot()
        
        # 筛选关注的股票
        df = df[df["代码"].isin(watch_codes)]
        
        # 数据清洗和格式调整
        # 重命名列，统一格式
        df.rename(columns={
            "代码": "股票代码",
            "名称": "股票名称",
            "最新价": "当前价格(元)",
            "涨跌幅": "涨跌幅(%)",
            "成交量": "成交量(手)"
        }, inplace=True)
        
        # 成交量转换为「万手」（除以10000）
        df["成交量(万手)"] = round(df["成交量(手)"] / 10000, 2)
        
        # 补充更新时间
        df["更新时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 只保留需要的列，删除冗余列
        df = df[[
            "股票代码", "股票名称", "当前价格(元)", 
            "涨跌幅(%)", "成交量(万手)", "更新时间"
        ]]
        
        # 处理数值格式（避免科学计数法）
        df["当前价格(元)"] = df["当前价格(元)"].round(2)
        df["涨跌幅(%)"] = df["涨跌幅(%)"].round(2)
        
        return df
    
    except Exception as e:
        # 捕获所有异常，返回友好提示
        st.error(f"❌ 获取真实数据失败：{str(e)[:100]}")
        st.info("💡 可能原因：非交易时间/网络问题/AkShare接口更新")
        # 异常时返回空DataFrame，避免页面报错
        return pd.DataFrame()

# ====================== 数据展示 ======================
# 1. 实时股票数据模块
st.subheader("🔍 实时A股行情")
stock_df = get_real_a_stock_data(WATCH_STOCK_CODES)

if not stock_df.empty:
    # 美化展示：涨跌幅标红/绿
    def highlight_change(val):
        if val > 0:
            return 'background-color: #f0fff4; color: #0f5132'  # 涨：浅绿
        elif val < 0:
            return 'background-color: #fff5f5; color: #842029'  # 跌：浅红
        return ''
    
    styled_df = stock_df.style.applymap(highlight_change, subset=["涨跌幅(%)"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # 2. 异动提醒模块
    st.subheader("⚠️ 异动提醒")
    abnormal_stocks = stock_df[abs(stock_df["涨跌幅(%)"]) > ABNORMAL_THRESHOLD]
    
    if abnormal_stocks.empty:
        st.success(f"✅ 暂无异常波动股票（阈值：±{ABNORMAL_THRESHOLD}%）")
    else:
        st.warning(f"🔴 发现 {len(abnormal_stocks)} 只股票波动异常：")
        st.dataframe(
            abnormal_stocks.style.applymap(highlight_change, subset=["涨跌幅(%)"]),
            use_container_width=True,
            hide_index=True
        )
else:
    # 数据为空时的友好提示
    st.info("ℹ️ 暂无可用数据，请检查：")
    st.markdown("""
    - 是否为A股交易时间（9:30-11:30 / 13:00-15:00）
    - requirements.txt 是否包含 akshare==1.10.0
    - 网络是否正常（Streamlit Cloud 需能访问AkShare）
    """)

# ====================== 底部信息 ======================
st.divider()
st.caption(f"📅 最后检查时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("📢 数据来源：AkShare（A股实时行情接口）")
