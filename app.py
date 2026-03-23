import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, time
import smtplib
from email.mime.text import MIMEText
import numpy as np
import time

# ====================== 配置区 ======================
API_KEY = "346PQPUMN005B74Q"          # 你的 Alpha Vantage 密钥（马股用）
INITIAL_CAPITAL = 20000
POSITION_LIMIT = 0.05
RSI_PERIOD = 14
MA_PERIOD = 20
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15

# 邮件配置（必须替换为真实信息！）
EMAIL_CONFIG = {
    "sender": "你的邮箱@gmail.com",
    "password": "你的Gmail授权码",
    "receiver": "接收邮箱@example.com",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
}

# ====================== 股票池 ======================
STOCK_POOL = {
    "🇺🇸 美股": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "ADBE", "ORCL",
        "V", "MA", "JPM", "DIS", "NFLX",
        "INTC", "CSCO", "PEP", "KO", "WMT"
    ],
    "🇲🇾 马股": [
        "1155.KL", "5235.KL", "5168.KL", "1082.KL", "1295.KL",
        "5347.KL", "3182.KL", "6012.KL", "5819.KL", "4065.KL",
        "4162.KL", "6947.KL", "7084.KL", "7113.KL", "7251.KL",
        "7285.KL", "7293.KL", "7315.KL", "7363.KL", "7412.KL"
    ],
    "🇭🇰 港股": [
        "0700.HK", "9988.HK", "0005.HK", "0001.HK", "0002.HK",
        "0003.HK", "0006.HK", "0388.HK", "0939.HK", "1398.HK",
        "2318.HK", "2628.HK", "3988.HK", "1299.HK", "0011.HK",
        "0012.HK", "0016.HK", "0019.HK", "0027.HK", "0066.HK"
    ],
    "🇨🇳 A股": [
        "600036.SS", "600519.SS", "000001.SZ", "000858.SZ",
        "000651.SZ", "002594.SZ", "300750.SZ", "600900.SS",
        "601318.SS", "601398.SS", "601288.SS", "601988.SS",
        "601328.SS", "600030.SS", "600016.SS", "600276.SS",
        "600309.SS", "600436.SS", "600519.SS", "601888.SS"
    ]
}

# ====================== 数据获取函数 ======================
def get_stock_data_alpha_vantage(symbol):
    """使用 Alpha Vantage 获取马股数据（带限流处理）"""
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}&apikey={API_KEY}&outputsize=compact"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if "Time Series (Daily)" not in data:
            if "Note" in data:
                st.warning(f"{symbol}: {data['Note']}")
            else:
                st.warning(f"{symbol}: 无数据返回")
            return None

        df = pd.DataFrame(data["Time Series (Daily)"]).T
        df = df.rename(columns={
            "1. open": "Open", "2. high": "High", "3. low": "Low",
            "4. close": "Close", "5. volume": "Volume"
        })
        df = df.astype({col: float for col in ["Open", "High", "Low", "Close", "Volume"]})
        df = df.sort_index().tail(90)

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
        st.warning(f"{symbol}: 请求超时")
        return None
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            st.warning(f"API调用频率过高，暂停60秒")
            time.sleep(60)
        else:
            st.warning(f"{symbol}: HTTP错误 {e}")
        return None
    except Exception as e:
        st.warning(f"{symbol}: 未知错误 {e}")
        return None

def get_stock_data_yfinance(symbol):
    """使用 yfinance 获取非马股数据"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="3mo")
        if df.empty:
            st.warning(f"⚠️ {symbol}: 无数据")
            return None

        if len(df) < MA_PERIOD + RSI_PERIOD:
            st.warning(f"⚠️ {symbol}: 数据不足 {len(df)} 天")
            return None

        df["MA20"] = df["Close"].rolling(MA_PERIOD).mean()
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
        loss = -delta.where(delta < 0, 0).rolling(RSI_PERIOD).mean()
        rs = gain / loss.replace(0, 1e-8)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["Vol_MA20"] = df["Volume"].rolling(MA_PERIOD).mean()
        df["10d_Change"] = (df["Close"] / df["Close"].shift(10).replace(0, 1e-8) - 1) * 100

        return df.iloc[-1]

    except Exception as e:
        st.warning(f"❌ {symbol}: 异常 - {str(e)}")
        return None

def get_stock_data(symbol, market):
    """根据市场选择数据源"""
    if market == "🇲🇾 马股":
        return get_stock_data_alpha_vantage(symbol)
    else:
        return get_stock_data_yfinance(symbol)

def generate_signal(row):
    if row is None or pd.isna(row["MA20"]) or pd.isna(row["RSI"]):
        return "无数据"
    long_cond = (row["Close"] > row["MA20"] and 30 < row["RSI"] < 70 and
                 row["Volume"] > row["Vol_MA20"] and row["10d_Change"] > 3)
    short_cond = (row["Close"] < row["MA20"] or row["RSI"] > 70 or row["RSI"] < 30)
    return "🟢 进场信号" if long_cond else "🔴 出场信号" if short_cond else "⚪ 观望"

def send_report(report_content):
    if "你的邮箱" in EMAIL_CONFIG["sender"] or "授权码" in EMAIL_CONFIG["password"]:
        st.error("❌ 请先在代码中配置正确的邮箱和授权码！")
        return

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
        st.success("✅ 日报发送成功")
    except smtplib.SMTPAuthenticationError:
        st.error("❌ 邮件认证失败，请检查邮箱地址和授权码")
    except Exception as e:
        st.error(f"❌ 邮件发送失败: {e}")

# ====================== 页面布局 ======================
st.set_page_config(page_title="全球股市监控面板", page_icon="📈", layout="wide")
st.title("📈 全球股市实时监控（80只核心龙头）")
st.markdown("""
✅ **混合数据源**：美股/港股/A股使用 yfinance（免费），马股使用 Alpha Vantage（API Key已配置）。
""")

with st.sidebar:
    st.header("控制面板")
    force_refresh = st.button("🔄 强制刷新全部数据")
    send_now = st.button("📧 立即发送今日日报")
    st.markdown("---")
    st.info(f"**当前标的数**: {sum(len(v) for v in STOCK_POOL.values())} 只")

@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_data():
    all_results = {}
    total = sum(len(v) for v in STOCK_POOL.values())
    progress_bar = st.progress(0, text="正在获取数据...")
    status_text = st.empty()

    idx = 0
    for market, symbols in STOCK_POOL.items():
        market_data = []
        for symbol in symbols:
            status_text.text(f"正在处理 {market} - {symbol}...")
            data = get_stock_data(symbol, market)
            if data is not None:
                signal = generate_signal(data)
                market_data.append({
                    "代码": symbol,
                    "当前价": round(data["Close"], 2),
                    "MA20": round(data["MA20"], 2) if not pd.isna(data["MA20"]) else "-",
                    "RSI": round(data["RSI"], 2) if not pd.isna(data["RSI"]) else "-",
                    "10日涨幅%": round(data["10d_Change"], 2) if not pd.isna(data["10d_Change"]) else "-",
                    "信号": signal
                })
            else:
                market_data.append({
                    "代码": symbol,
                    "当前价": "-",
                    "MA20": "-",
                    "RSI": "-",
                    "10日涨幅%": "-",
                    "信号": "获取失败"
                })
            idx += 1
            progress_bar.progress(idx / total)
            # 控制请求频率（Alpha Vantage 限流）
            if market == "🇲🇾 马股":
                time.sleep(12)  # 每分钟5次
            # yfinance 无需等待，但可留一点缓冲
            else:
                time.sleep(0.5)

        all_results[market] = market_data
    progress_bar.empty()
    status_text.empty()
    return all_results

if force_refresh:
    st.cache_data.clear()
    st.success("缓存已清除，开始重新获取所有数据...")
    data_dict = fetch_all_data()
else:
    data_dict = fetch_all_data()

# 展示数据
for market, records in data_dict.items():
    if records:
        df = pd.DataFrame(records)
        def highlight_signal(s):
            if s == "🟢 进场信号":
                return "background-color: #d4edda; color: #155724"
            elif s == "🔴 出场信号":
                return "background-color: #f8d7da; color: #721c24"
            else:
                return ""

        styled_df = df.style.map(highlight_signal, subset=["信号"])
        st.subheader(market)
        st.dataframe(styled_df, width='stretch', hide_index=True)
    else:
        st.warning(f"{market} 无数据")

if send_now:
    with st.spinner("正在生成日报并发送..."):
        report = f"=== 全球市场日报 {datetime.now().strftime('%Y-%m-%d')} ===\n"
        report += f"初始资金：{INITIAL_CAPITAL} MYR | 单仓上限：{POSITION_LIMIT*100}%\n\n"
        for market, records in data_dict.items():
            report += f"--- {market} ---\n"
            for r in records:
                report += f"{r['代码']}: 现价{r['当前价']} | {r['信号']}\n"
        send_report(report)

st.divider()
st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据源：yfinance + Alpha Vantage | 马股数据每分钟限5次请求")
