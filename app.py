import streamlit as st
import pandas as pd
import requests
from datetime import datetime, time
import smtplib
from email.mime.text import MIMEText
import numpy as np
import time  # 新增：控制API频率

# ====================== 配置区 ======================
API_KEY = "346PQPUMN005B74Q"  # 你的Alpha Vantage Key
INITIAL_CAPITAL = 20000  # 初始资金（马币）
POSITION_LIMIT = 0.05    # 单只仓位≤5%
RSI_PERIOD = 14
MA_PERIOD = 20
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15

# 核心标的池（仅保留Alpha Vantage明确支持的龙头，总计40只）
STOCK_POOL = {
    # 🇺🇸 美股15只（支持最好，全保留）
    "美股核心": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "ADBE", "ORCL",
        "V", "MA", "JPM", "DIS", "NFLX"
    ],
    # 🇲🇾 马股10只（Alpha Vantage支持的核心龙头）
    "马股核心": [
        "1155.KL", "5235.KL", "5168.KL", "1082.KL", "1295.KL",
        "5347.KL", "3182.KL", "6012.KL", "5819.KL", "4065.KL"
    ],
    # 🇭🇰 港股8只（核心龙头）
    "港股核心": [
        "0700.HK", "9988.HK", "0005.HK", "0001.HK", "0002.HK",
        "0003.HK", "0006.HK", "0388.HK"
    ],
    # 🇨🇳 A股7只（Alpha Vantage支持的核心龙头，格式已修正）
    "A股核心": [
        "600036.SS", "600519.SS", "000001.SZ", "000858.SZ",
        "000651.SZ", "002594.SZ", "300750.SZ"
    ]
}

# 邮件配置（替换为你的真实信息！）
EMAIL_CONFIG = {
    "sender": "你的邮箱@gmail.com",
    "password": "你的Gmail授权码",  # 应用专用密码
    "receiver": "你的接收邮箱@xxx.com",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
}

# ====================== 工具函数（优化版） ======================
@st.cache_data(ttl=900)  # 缓存15分钟，减少调用
def get_stock_data_alpha_vantage(symbol):
    """从Alpha Vantage获取数据（带容错）"""
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}&apikey={API_KEY}&outputsize=full"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # 新增：捕获HTTP错误
        data = response.json()
        
        if "Time Series (Daily)" not in data:
            return None  # 无数据直接返回
        
        df = pd.DataFrame(data["Time Series (Daily)"]).T
        df = df.rename(columns={
            "1. open": "Open", "2. high": "High", "3. low": "Low",
            "4. close": "Close", "5. volume": "Volume"
        })
        df = df.astype({"Open": float, "High": float, "Low": float, "Close": float, "Volume": float})
        df = df.sort_index().tail(90)  # 取最近3个月
        
        if len(df) < MA_PERIOD + RSI_PERIOD:
            return None
        
        # 计算技术指标
        df["MA20"] = df["Close"].rolling(MA_PERIOD).mean()
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
        loss = -delta.where(delta < 0, 0).rolling(RSI_PERIOD).mean()
        rs = gain / loss.replace(0, 1e-8)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["Vol_MA20"] = df["Volume"].rolling(MA_PERIOD).mean()
        df["10d_Change"] = (df["Close"] / df["Close"].shift(10).replace(0, 1e-8) - 1) * 100
        
        return df.iloc[-1]
    
    except requests.exceptions.Timeout:
        st.warning(f"{symbol}：请求超时")
        return None
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            st.warning(f"API调用频率过高，暂停1分钟")
            time.sleep(60)  # 新增：频率超限时自动暂停
        return None
    except Exception:
        return None

def generate_signal(row):
    """生成买卖信号"""
    if row is None or pd.isna(row["MA20"]) or pd.isna(row["RSI"]):
        return "无数据"
    long_cond = (row["Close"] > row["MA20"] and 30 < row["RSI"] < 70 and row["Volume"] > row["Vol_MA20"] and row["10d_Change"] > 3)
    short_cond = (row["Close"] < row["MA20"] or row["RSI"] > 70 or row["RSI"] < 30)
    return "🟢 进场信号" if long_cond else "🔴 出场信号" if short_cond else "⚪ 观望"

def send_daily_report(report_content):
    """发送每日报告"""
    if datetime.now().time() < time(18, 0):
        st.info("ℹ️ 未到18:00，测试可忽略")
    msg = MIMEText(report_content, "plain", "utf-8")
    msg["Subject"] = f"全球市场日报 {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = EMAIL_CONFIG["sender"]
    msg["To"] = EMAIL_CONFIG["receiver"]
    
    try:
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.starttls()
        server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
        server.sendmail(EMAIL_CONFIG["sender"], EMAIL_CONFIG["receiver"], msg.as_string())
        server.quit()
        st.success("✅ 日报已发送")
    except Exception as e:
        st.error(f"❌ 邮件发送失败：{e}")

# ====================== 页面展示 ======================
st.set_page_config(page_title="全球市场监控面板", page_icon="📊", layout="wide")
st.title("📊 全球市场监控面板（核心龙头版）")

# 遍历市场获取数据
all_signals = []
for market, symbols in STOCK_POOL.items():
    st.subheader(f"📌 {market}")
    market_data = []
    for i, sym in enumerate(symbols):
        # 每3个标的暂停6秒，彻底避免429限流
        if i % 3 == 0 and i > 0:
            time.sleep(6)
        
        data = get_stock_data_alpha_vantage(sym)
        if data is not None:
            signal = generate_signal(data)
            market_data.append({
                "代码": sym,
                "当前价": round(data["Close"], 2),
                "MA20": round(data["MA20"], 2) if not pd.isna(data["MA20"]) else "-",
                "RSI": round(data["RSI"], 2) if not pd.isna(data["RSI"]) else "-",
                "10日涨幅": round(data["10d_Change"], 2) if not pd.isna(data["10d_Change"]) else "-",
                "信号": signal
            })
            if signal in ["🟢 进场信号", "🔴 出场信号"]:
                st.toast(f"{sym}：{signal}！", icon=signal[0])
    
    if market_data:
        df = pd.DataFrame(market_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        all_signals.extend(market_data)
    else:
        st.info(f"{market} 暂无可用数据（非交易时间/标的不支持）")

# 生成日报按钮
if st.button("📧 生成并发送今日日报"):
    with st.spinner("正在生成日报..."):
        try:
            report = f"=== 全球市场日报 {datetime.now().strftime('%Y-%m-%d')} ===\n初始资金：{INITIAL_CAPITAL} MYR | 单仓上限：{POSITION_LIMIT*100}%\n\n"
            for market, symbols in STOCK_POOL.items():
                report += f"--- {market} ---\n"
                for i, sym in enumerate(symbols):
                    if i % 3 == 0 and i > 0:
                        time.sleep(6)
                    data = get_stock_data_alpha_vantage(sym)
                    if data:
                        sig = generate_signal(data)
                        report += f"{sym}: 现价{data['Close']:.2f} | {sig}\n"
            send_daily_report(report)
        except Exception as e:
            st.error(f"❌ 日报生成失败：{str(e)}")

st.divider()
st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据源：Alpha Vantage（免费版） | 标的总数：{sum(len(v) for v in STOCK_POOL.values())}只（核心龙头）")
