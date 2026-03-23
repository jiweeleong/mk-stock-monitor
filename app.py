import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import akshare as ak  # 新增这一行

# 设置页面标题
st.title("我的股票监控面板")

# --- 1. 定义要监控的股票代码（简化版，优先保证能运行）---
# 先选美股（yfinance 最稳定），A股/港股可能因网络问题获取失败
stock_list = {
    "AAPL": "苹果公司",
    "MSFT": "微软公司",
    "GOOG": "谷歌公司"
}

# --- 2. 拉取实时数据（增加异常处理）---
@st.cache_data(ttl=60)  # 缓存1分钟
def get_real_time_stock_data(stock_list):
    data = []
    for code, name in stock_list.items():
        try:  # 单个股票出错不影响整体
            ticker = yf.Ticker(code)
            # 优先获取基础信息，避免hist为空
            info = ticker.info
            current_price = info.get("currentPrice", info.get("previousClose", 0))
            prev_close = info.get("previousClose", current_price)
            
            if current_price == 0 or prev_close == 0:
                continue  # 数据为空则跳过
            
            # 计算涨跌幅
            change_pct = (current_price - prev_close) / prev_close * 100
            # 成交量（用info里的最新成交量，避免hist为空）
            volume = info.get("volume", 0) / 10000  # 转换为万手
            
            data.append({
                "股票代码": code,
                "股票名称": name,
                "当前价格": round(current_price, 2),
                "涨跌幅(%)": round(change_pct, 2),
                "成交量(万手)": round(volume, 2),
                "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            st.warning(f"获取 {code} ({name}) 数据失败：{str(e)[:50]}")
            continue
    
    # 确保DataFrame有列，避免KeyError
    df = pd.DataFrame(data)
    if "涨跌幅(%)" not in df.columns:
        df["涨跌幅(%)"] = []
    return df

# --- 3. 展示数据 ---
st.subheader("实时股票数据")
df = get_real_time_stock_data(stock_list)

if df.empty:
    st.info("暂无可用数据，请检查网络或股票代码")
else:
    st.dataframe(df, use_container_width=True)

    # --- 4. 异动提醒（增加列存在性检查）---
    st.subheader("异动提醒")
    threshold = 2.0  # 涨跌幅阈值±2%
    # 先检查列是否存在，再筛选
    if "涨跌幅(%)" in df.columns and not df["涨跌幅(%)"].empty:
        abnormal = df[(abs(df["涨跌幅(%)"]) > threshold)]
        if abnormal.empty:
            st.success("暂无异常波动股票")
        else:
            st.warning("以下股票波动异常：")
            st.dataframe(abnormal, use_container_width=True)
    else:
        st.info("暂无涨跌幅数据")

# --- 5. 最后更新时间 ---
st.caption(f"最后更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
