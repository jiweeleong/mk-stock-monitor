import streamlit as st
import pandas as pd
import requests
from datetime import datetime, time
import yfinance as yf
import smtplib
from email.mime.text import MIMEText

# ====================== 配置区 ======================
API_KEY = "346PQPUMN005B74Q"  # 你的Alpha Vantage Key
INITIAL_CAPITAL = 20000  # 初始资金（马币）
POSITION_LIMIT = 0.05    # 单只仓位≤5%
RSI_PERIOD = 14
MA_PERIOD = 20
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15

# 标的池（示例，可替换为你MOOMOO里的50只）
# 标的池（马股50+港股50+美股50+A股50，适配趋势+动量策略）
STOCK_POOL = {
    # 🇲🇾 马股50（KLCI成分股，流动性最佳）
    "马股50": [
        "1155.KL", "5235.KL", "5168.KL", "1082.KL", "1295.KL",
        "5347.KL", "3182.KL", "6012.KL", "5819.KL", "4065.KL",
        "1023.KL", "2445.KL", "5014.KL", "5246.KL", "6947.KL",
        "1961.KL", "4707.KL", "7277.KL", "1066.KL", "5184.KL",
        "3034.KL", "4502.KL", "5296.KL", "6033.KL", "7164.KL",
        "1171.KL", "4197.KL", "5248.KL", "6888.KL", "7084.KL",
        "1015.KL", "2185.KL", "5024.KL", "5681.KL", "6399.KL",
        "1269.KL", "3816.KL", "5120.KL", "6068.KL", "7247.KL",
        "1028.KL", "2859.KL", "5218.KL", "6007.KL", "7100.KL",
        "1086.KL", "3239.KL", "5304.KL", "6599.KL", "7221.KL"
    ],
    # 🇭🇰 港股50（恒生指数+科技龙头，波动适中）
    "港股50": [
        "0700.HK", "9988.HK", "0005.HK", "0001.HK", "0002.HK",
        "0003.HK", "0006.HK", "0011.HK", "0012.HK", "0016.HK",
        "0017.HK", "0027.HK", "0066.HK", "0083.HK", "0101.HK",
        "0151.HK", "0175.HK", "0267.HK", "0288.HK", "0386.HK",
        "0388.HK", "0669.HK", "0688.HK", "0700.HK", "0762.HK",
        "0823.HK", "0836.HK", "0857.HK", "0883.HK", "0939.HK",
        "0941.HK", "1038.HK", "1044.HK", "1088.HK", "1109.HK",
        "1113.HK", "1177.HK", "1211.HK", "1299.HK", "1398.HK",
        "1810.HK", "1876.HK", "1928.HK", "2007.HK", "2018.HK",
        "2313.HK", "2318.HK", "2328.HK", "2382.HK", "2628.HK"
    ],
    # 🇺🇸 美股50（标普500+科技龙头，趋势清晰）
    "美股50": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "ADBE", "ORCL",
        "IBM", "INTC", "QCOM", "TXN", "AVGO",
        "V", "MA", "PYPL", "AXP", "DFS",
        "JPM", "BAC", "WFC", "C", "GS",
        "MS", "BLK", "SCHW", "T", "VZ",
        "TMUS", "DIS", "NFLX", "CMCSA", "PARA",
        "PEP", "KO", "MCD", "SBUX", "YUM",
        "PG", "JNJ", "PFE", "MRK", "ABT",
        "AMGN", "GILD", "BMY", "LLY", "REGN"
    ],
    # 🇨🇳 A股50（沪深300+行业龙头，波动适中）
    "A股50": [
        "600000.SHH", "600036.SHH", "600519.SHH", "600887.SHH", "601318.SHH",
        "601628.SHH", "601857.SHH", "601988.SHH", "600030.SHH", "600276.SHH",
        "600309.SHH", "600585.SHH", "600699.SHH", "600809.SHH", "601012.SHH",
        "601166.SHH", "601211.SHH", "601225.SHH", "601336.SHH", "601601.SHH",
        "601888.SHH", "603259.SHH", "603260.SHH", "603288.SHH", "603501.SHH",
        "000001.SZS", "000002.SZS", "000063.SZS", "000157.SZS", "000333.SZS",
        "000568.SZS", "000651.SZS", "000725.SZS", "000858.SZS", "000977.SZS",
        "002027.SZS", "002304.SZS", "002352.SZS", "002415.SZS", "002475.SZS",
        "002594.SZS", "002602.SZS", "002714.SZS", "002812.SZS", "002916.SZS",
        "300059.SZS", "300124.SZS", "300274.SZS", "300450.SZS", "300750.SZS"
    ]
}

# 邮件配置（用于每日报告）
EMAIL_CONFIG = {
    "sender": "你的邮箱@gmail.com",
    "password": "你的邮箱授权码",
    "receiver": "你的邮箱@xxx.com",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
}

# ====================== 工具函数 ======================
@st.cache_data(ttl=300)
def get_stock_data(symbol):
    """获取历史数据+技术指标"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo", interval="1d")
        if len(hist) < MA_PERIOD + RSI_PERIOD:
            return None
        
        # 计算20日均线
        hist["MA20"] = hist["Close"].rolling(MA_PERIOD).mean()
        # 计算RSI
        delta = hist["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss
        hist["RSI"] = 100 - (100 / (1 + rs))
        # 计算成交量均线
        hist["Vol_MA20"] = hist["Volume"].rolling(MA_PERIOD).mean()
        # 10日涨幅
        hist["10d_Change"] = (hist["Close"] / hist["Close"].shift(10) - 1) * 100
        return hist.iloc[-1]  # 返回最新一天数据
    except:
        return None

def generate_signal(row):
    """生成买卖信号"""
    if row is None:
        return "无数据"
    signals = []
    # 进场条件
    long_cond = (
        row["Close"] > row["MA20"] and
        30 < row["RSI"] < 70 and
        row["Volume"] > row["Vol_MA20"] and
        row["10d_Change"] > 3
    )
    # 出场条件
    short_cond = (
        row["Close"] < row["MA20"] or
        row["RSI"] > 70 or row["RSI"] < 30
    )
    if long_cond:
        return "🟢 进场信号"
    elif short_cond:
        return "🔴 出场信号"
    else:
        return "⚪ 观望"

def send_daily_report(report_content):
    """发送每日18:00邮件报告"""
    if datetime.now().time() < time(18, 0):
        return
    msg = MIMEText(report_content, "plain", "utf-8")
    msg["Subject"] = f"股票市场日报 {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = EMAIL_CONFIG["sender"]
    msg["To"] = EMAIL_CONFIG["receiver"]
    
    try:
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.starttls()
        server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
        server.sendmail(EMAIL_CONFIG["sender"], EMAIL_CONFIG["receiver"], msg.as_string())
        server.quit()
        st.success("✅ 日报已发送至邮箱")
    except Exception as e:
        st.error(f"❌ 邮件发送失败：{e}")

# ====================== 页面展示 ======================
st.set_page_config(page_title="全球市场监控面板", page_icon="📊", layout="wide")
st.title("📊 全球市场监控面板（MOOMOO马来西亚版）")

# 遍历市场获取信号
all_signals = []
for market, symbols in STOCK_POOL.items():
    st.subheader(f"📌 {market}")
    market_data = []
    for sym in symbols:
        data = get_stock_data(sym)
        if data is not None:
            signal = generate_signal(data)
            market_data.append({
                "代码": sym,
                "当前价": round(data["Close"], 2),
                "MA20": round(data["MA20"], 2),
                "RSI": round(data["RSI"], 2),
                "10日涨幅": round(data["10d_Change"], 2),
                "信号": signal
            })
            if signal in ["🟢 进场信号", "🔴 出场信号"]:
                st.toast(f"{sym}：{signal}！", icon=signal[0])
    if market_data:
        df = pd.DataFrame(market_data)
        st.dataframe(df, use_container_width=True)
        all_signals.extend(market_data)

# 生成日报
if st.button("📧 生成并发送今日日报"):
    report = f"=== 全球市场日报 {datetime.now().strftime('%Y-%m-%d')} ===\n"
    report += f"初始资金：{INITIAL_CAPITAL} MYR | 单仓上限：{POSITION_LIMIT*100}%\n\n"
    for market, symbols in STOCK_POOL.items():
        report += f"--- {market} ---\n"
        for sym in symbols:
            data = get_stock_data(sym)
            if data:
                sig = generate_signal(data)
                report += f"{sym}: 现价{data['Close']:.2f} | {sig}\n"
    send_daily_report(report)

st.divider()
st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 策略：趋势+动量双因子")
