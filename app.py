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

# 标的池（每个市场25只核心标的，适配趋势+动量策略）
STOCK_POOL = {
    # 🇲🇾 马股25（KLCI核心成分股，流动性最佳）
    "马股25": [
        "1155.KL", "5235.KL", "5168.KL", "1082.KL", "1295.KL",
        "5347.KL", "3182.KL", "6012.KL", "5819.KL", "4065.KL",
        "1023.KL", "2445.KL", "5014.KL", "5246.KL", "6947.KL",
        "1961.KL", "4707.KL", "7277.KL", "1066.KL", "5184.KL",
        "3034.KL", "4502.KL", "5296.KL", "6033.KL", "7164.KL"
    ],
    # 🇭🇰 港股25（恒生指数核心龙头，波动适中）
    "港股25": [
        "0700.HK", "9988.HK", "0005.HK", "0001.HK", "0002.HK",
        "0003.HK", "0006.HK", "0011.HK", "0012.HK", "0016.HK",
        "0017.HK", "0027.HK", "0066.HK", "0083.HK", "0101.HK",
        "0151.HK", "0175.HK", "0267.HK", "0288.HK", "0386.HK",
        "0388.HK", "0669.HK", "0688.HK", "0762.HK", "0823.HK"
    ],
    # 🇺🇸 美股25（标普500科技/金融龙头，趋势清晰）
    "美股25": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "ADBE", "ORCL",
        "V", "MA", "PYPL", "AXP", "JPM",
        "BAC", "WFC", "C", "GS", "MS",
        "DIS", "NFLX", "PEP", "KO", "MCD"
    ],
    # 🇨🇳 A股25（沪深300核心龙头，波动适中）
    "A股25": [
        "600000.SHH", "600036.SHH", "600519.SHH", "600887.SHH", "601318.SHH",
        "601628.SHH", "601857.SHH", "601988.SHH", "600030.SHH", "600276.SHH",
        "000001.SZS", "000002.SZS", "000063.SZS", "000333.SZS", "000858.SZS",
        "000651.SZS", "002027.SZS", "002304.SZS", "002594.SZS", "002415.SZS",
        "300059.SZS", "300124.SZS", "300274.SZS", "300450.SZS", "300750.SZS"
    ]
}

# 邮件配置（替换为你的真实信息！）
EMAIL_CONFIG = {
    "sender": "你的邮箱@gmail.com",
    "password": "你的Gmail授权码",  # 不是登录密码，需生成应用专用密码
    "receiver": "你的接收邮箱@xxx.com",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
}

# ====================== 工具函数（修复版） ======================
@st.cache_data(ttl=600)  # 延长缓存到10分钟，减少API压力
def get_stock_data(symbol):
    """获取历史数据+技术指标（带超时和异常处理）"""
    try:
        ticker = yf.Ticker(symbol)
        # 增加超时限制，避免卡慢
        hist = ticker.history(period="3mo", interval="1d", timeout=10)
        if len(hist) < MA_PERIOD + RSI_PERIOD:
            st.warning(f"{symbol} 数据量不足，跳过")
            return None
        
        # 计算20日均线
        hist["MA20"] = hist["Close"].rolling(MA_PERIOD).mean()
        # 计算RSI（修复除以0报错）
        delta = hist["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
        rs = gain / loss.replace(0, 1e-8)  # 避免除以0
        hist["RSI"] = 100 - (100 / (1 + rs))
        # 计算成交量均线
        hist["Vol_MA20"] = hist["Volume"].rolling(MA_PERIOD).mean()
        # 10日涨幅（修复除以0）
        hist["10d_Change"] = (hist["Close"] / hist["Close"].shift(10).replace(0, 1e-8) - 1) * 100
        return hist.iloc[-1]
    except requests.exceptions.Timeout:
        st.warning(f"{symbol} 数据获取超时，跳过")
        return None
    except Exception as e:
        st.warning(f"{symbol} 数据获取失败：{str(e)[:50]}")
        return None

def generate_signal(row):
    """生成买卖信号"""
    if row is None:
        return "无数据"
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
    """发送每日18:00邮件报告（带友好提示）"""
    if datetime.now().time() < time(18, 0):
        st.info("ℹ️ 未到18:00，若需测试可手动修改时间或忽略此提示")
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
        st.info("💡 请检查：1.邮箱授权码是否正确 2.是否开启两步验证 3.SMTP服务器配置")

# ====================== 页面展示（优化版） ======================
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
            # 信号弹窗提醒
            if signal in ["🟢 进场信号", "🔴 出场信号"]:
                st.toast(f"{sym}：{signal}！", icon=signal[0])
    # 展示数据表格
    if market_data:
        df = pd.DataFrame(market_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        all_signals.extend(market_data)
    else:
        st.info(f"{market} 暂无可用数据（可能非交易时间）")

# 生成日报按钮（带加载动画和异常捕获）
if st.button("📧 生成并发送今日日报"):
    with st.spinner("正在生成日报..."):
        try:
            report = f"=== 全球市场日报 {datetime.now().strftime('%Y-%m-%d')} ===\n"
            report += f"初始资金：{INITIAL_CAPITAL} MYR | 单仓上限：{POSITION_LIMIT*100}%\n\n"
            for market, symbols in STOCK_POOL.items():
                report += f"--- {market} ---\n"
                for sym in symbols:
                    data = get_stock_data(sym)
                    if data:
                        sig = generate_signal(data)
                        report += f"{sym}: 现价{data['Close']:.2f} | {sig}\n"
            # 发送日报
            send_daily_report(report)
        except Exception as e:
            st.error(f"❌ 日报生成失败：{str(e)}")

st.divider()
st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 策略：趋势+动量双因子 | 标的总数：100只")
