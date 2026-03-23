import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# 设置页面标题
st.title("我的股票监控面板")

# --- 1. 定义要监控的股票代码（示例：A股/港股/美股）---
# A股需要加 .SH 或 .SZ 后缀，港股加 .HK，美股直接代码
stock_list = {
    "600000.SH": "浦发银行",
    "000001.SZ": "平安银行",
    "300059.SZ": "东方财富",
    "0700.HK": "腾讯控股",  # 港股示例
    "AAPL": "苹果公司"      # 美股示例
}

# --- 2. 拉取实时数据 ---
@st.cache_data(ttl=60)  # 缓存1分钟，避免频繁请求
def get_real_time_stock_data(stock_list):
    data = []
    for code, name in stock_list.items():
        ticker = yf.Ticker(code)
        # 获取最新1天的行情数据（实时/近一天）
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            latest = hist.iloc[-1]
            prev_close = ticker.info.get("previousClose", latest["Close"])
            change_pct = (latest["Close"] - prev_close) / prev_close * 100
            volume = latest["Volume"] / 10000  # 转换为万手
            data.append({
                "股票代码": code,
                "股票名称": name,
                "当前价格": round(latest["Close"], 2),
                "涨跌幅(%)": round(change_pct, 2),
                "成交量(万手)": round(volume, 2),
                "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    return pd.DataFrame(data)

# --- 3. 展示数据 ---
st.subheader("实时股票数据")
df = get_real_time_stock_data(stock_list)
st.dataframe(df, use_container_width=True)

# --- 4. 异动提醒 ---
st.subheader("异动提醒")
threshold = 2.0  # 自定义涨跌幅阈值（±2%）
abnormal = df[(abs(df["涨跌幅(%)"]) > threshold)]
if abnormal.empty:
    st.success("暂无异常波动股票")
else:
    st.warning("以下股票波动异常：")
    st.dataframe(abnormal, use_container_width=True)

# --- 5. 最后更新时间 ---
st.caption(f"最后更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
