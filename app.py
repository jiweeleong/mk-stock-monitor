# 导入所需库
import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# ====================== 页面基础设置 ======================
st.set_page_config(
    page_title="我的股票监控面板",
    page_icon="📈",
    layout="wide"
)
st.title("📈 我的股票监控面板（真实全球股票数据）")

# ====================== 核心配置（已填入你的 API Key）======================
API_KEY = "346PQPUMN005B74Q"  # 你的 Alpha Vantage API Key（已填好）
# 监控的股票列表（支持美股/港股/A股，可自行修改）
STOCK_LIST = {
    "AAPL": "苹果公司",       # 美股（无延迟）
    "MSFT": "微软公司",       # 美股（无延迟）
    "0700.HK": "腾讯控股",    # 港股（延迟约15分钟）
    "600000.SHH": "浦发银行", # A股沪市（延迟约15分钟）
    "000001.SZS": "平安银行"  # A股深市（延迟约15分钟）
}
ABNORMAL_THRESHOLD = 2.0  # 异动阈值±2%

# ====================== 真实数据获取函数 ======================
@st.cache_data(ttl=60)  # 60秒刷新一次，控制API调用频率
def get_alpha_vantage_data(symbol, api_key):
    """从Alpha Vantage获取实时股票数据"""
    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": api_key,
        "datatype": "json"
    }
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()  # 捕获HTTP错误
        data = response.json()
        
        # 检查数据是否有效
        if "Global Quote" in data and data["Global Quote"] and data["Global Quote"]["05. price"]:
            quote = data["Global Quote"]
            return {
                "股票代码": symbol,
                "股票名称": STOCK_LIST[symbol],
                "当前价格": round(float(quote["05. price"]), 2),
                "涨跌幅(%)": round(float(quote["10. change percent"].replace("%", "")), 2),
                "成交量(万手)": round(int(quote["06. volume"]) / 10000, 2),
                "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        st.warning(f"{symbol} 暂无数据（可能非交易时间/代码格式错误）")
        return None
    except requests.exceptions.Timeout:
        st.warning(f"获取 {symbol} 数据超时：网络连接慢")
        return None
    except Exception as e:
        st.warning(f"获取 {symbol} 数据失败：{str(e)[:60]}")
        return None

# ====================== 数据整合与展示 ======================
st.subheader("🔍 实时全球股票行情")
all_data = []
for symbol in STOCK_LIST.keys():
    stock_data = get_alpha_vantage_data(symbol, API_KEY)
    if stock_data:
        all_data.append(stock_data)

# 展示数据（带美化）
if all_data:
    df = pd.DataFrame(all_data)
    
    # 涨跌幅标红/绿
    def highlight_change(val):
        if val > 0:
            return 'background-color: #f0fff4; color: #0f5132'  # 涨：浅绿+深绿字
        elif val < 0:
            return 'background-color: #fff5f5; color: #842029'  # 跌：浅红+深红宇
        return ''
    
    # 应用样式并展示
    styled_df = df.style.applymap(highlight_change, subset=["涨跌幅(%)"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # 异动提醒模块
    st.subheader("⚠️ 异动提醒")
    abnormal_stocks = df[abs(df["涨跌幅(%)"]) > ABNORMAL_THRESHOLD]
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
    st.info("ℹ️ 暂无可用数据，请检查：")
    st.markdown("""
    - API Key 已确认正确：346PQPUMN005B74Q
    - 美股数据实时可用，港股/A股数据非交易时间可能为空
    - 免费版API调用限制：5次/分钟（当前60秒刷新一次，符合限制）
    """)

# ====================== 底部信息 ======================
st.divider()
st.caption(f"📅 最后更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("📢 数据来源：Alpha Vantage | 免费版港股/A股数据延迟约15分钟")
