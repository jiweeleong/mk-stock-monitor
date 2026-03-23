import streamlit as st
import pandas as pd
import requests
from datetime import datetime, time
import smtplib
from email.mime.text import MIMEText
import numpy as np

# ====================== 配置区 ======================
API_KEY = "346PQPUMN005B74Q"  # 你的Alpha Vantage Key
INITIAL_CAPITAL = 20000  # 初始资金（马币）
POSITION_LIMIT = 0.05    # 单只仓位≤5%
RSI_PERIOD = 14
MA_PERIOD = 20
STOP_LOSS = 0.08
TAKE_PROFIT = 0.15

# 标的池（每个市场25只核心标的，适配Alpha Vantage格式）
STOCK_POOL = {
    # 🇲🇾 马股25（Alpha Vantage格式：代码.KL）
    "马股25": [
        "1155.KL", "5235.KL", "5168.KL", "1082.KL", "1295.KL",
        "5347.KL", "3182.KL", "6012.KL", "5819.KL", "4065.KL",
        "1023.KL", "2445.KL", "5014.KL", "5246.KL", "6947.KL",
        "1961.KL", "4707.KL", "7277.KL", "1066.KL", "5184.KL",
        "3034.KL", "4502.KL", "5296.KL", "6033.KL", "7164.KL"
    ],
    # 🇭🇰 港股25（Alpha Vantage格式：代码.HK）
    "港股25": [
        "0700.HK", "9988.HK", "0005.HK", "0001.HK", "0002.HK",
        "0003.HK", "0006.HK", "0011.HK", "0012.HK", "0016.HK",
        "0017.HK", "0027.HK", "0066.HK", "0083.HK", "0101.HK",
        "0151.HK", "0175.HK", "0267.HK", "0288.HK", "0386.HK",
        "0388.HK", "0669.HK", "0688.HK", "0762.HK", "0823.HK"
    ],
    # 🇺🇸 美股25（Alpha Vantage格式：纯代码）
    "美股25": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "AMD", "ADBE", "ORCL",
        "V", "MA", "PYPL", "AXP", "JPM",
        "BAC", "WFC", "C", "GS", "MS",
        "DIS", "NFLX", "PEP", "KO", "MCD"
    ],
    # 🇨🇳 A股25（Alpha Vantage兼容格式：沪市=代码.SS，深市=代码.SZ）
    "A股25": [
        "600000.SS", "600036.SS", "600519.SS", "600887.SS", "601318.SS",
        "601628.SS", "601857.SS", "601988.SS", "600030.SS", "600276.SS",
        "000001.SZ", "000002.SZ", "000063.SZ", "000333.SZ", "000858.SZ",
        "000651.SZ", "002027.SZ", "002304.SZ", "002594.SZ", "002415.SZ",
        "300059.SZ", "300124.SZ", "300274.SZ", "300450.SZ", "300750.SZ"
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

# ====================== 工具函数（改用Alpha Vantage数据源） ======================
@st.cache_data(ttl=900)  # 缓存15分钟，适配API调用限制（5次/分钟）
def get_stock_data_alpha_vantage(symbol):
    """从Alpha Vantage获取历史数据+技术指标（适配所有市场）"""
    # 1. 获取日线数据
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}&apikey={API_KEY}&outputsize=full"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        
        # 检查是否返回有效数据
        if "Time Series (Daily)" not in data:
            st.warning(f"{symbol}：Alpha Vantage无数据（可能不支持该标的）")
            return None
        
        # 转换为DataFrame并排序
        df = pd.DataFrame(data["Time Series (Daily)"]).T
        df = df.rename(columns={
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume"
        })
        # 转换数据类型
        df = df.astype({
            "Open": float, "High": float, "Low": float,
            "Close": float, "Volume": float
        })
        df = df.sort_index()  # 按时间升序排列
        
        # 取最近3个月数据
        df = df.tail(90)
        if len(df) < MA_PERIOD + RSI_PERIOD:
            st.warning(f"{symbol} 数据量不足（仅{len(df)}条）")
            return None
        
        # 2. 计算技术指标
        # 20日均线
        df["MA20"] = df["Close"].rolling(window=MA_PERIOD).mean()
        # RSI
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=RSI_PERIOD).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss.replace(0, 1e-8)  # 避免除以0
        df["RSI"] = 100 - (100 / (1 + rs))
        # 20日均量
        df["Vol_MA20"] = df["Volume"].rolling(window=MA_PERIOD).mean()
        # 10日涨幅
        df["10d_Change"] = (df["Close"] / df["Close"].shift(10) - 1) * 100
        
        # 返回最新一条数据
        return df.iloc[-1]
    
    except requests.exceptions.Timeout:
        st.warning(f"{symbol}：请求超时")
        return None
    except Exception as e:
        st.warning(f"{symbol}：数据获取失败 - {str(e)[:50]}")
        return None

def generate_signal(row):
    """生成买卖信号"""
    if row is None:
        return "无数据"
    # 进场条件
    long_cond = (
        not pd.isna(row["MA20"]) and
        not pd.isna(row["RSI"]) and
        not pd.isna(row["Vol_MA20"]) and
        not pd.isna(row["10d_Change"]) and
        row["Close"] > row["MA20"] and
        30 < row["RSI"] < 70 and
        row["Volume"] > row["Vol_MA20"] and
        row["10d_Change"] > 3
    )
    # 出场条件
    short_cond = (
        not pd.isna(row["MA20"]) and
        not pd.isna(row["RSI"]) and
        (row["Close"] < row["MA20"] or row["RSI"] > 70 or row["RSI"] < 30)
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
        st.info("💡 排查建议：1.授权码是否正确 2.开启两步验证 3.SMTP端口是否匹配")

# ====================== 页面展示 ======================
st.set_page_config(page_title="全球市场监控面板", page_icon="📊", layout="wide")
st.title("📊 全球市场监控面板（MOOMOO马来西亚版）")

# 遍历市场获取信号
all_signals = []
for market, symbols in STOCK_POOL.items():
    st.subheader(f"📌 {market}")
    market_data = []
    # 控制API调用频率（避免5次/分钟限制）
    for i, sym in enumerate(symbols):
        # 每5个标的暂停12秒（适配5次/分钟限制）
        if i % 5 == 0 and i > 0:
            import time as t
            t.sleep(12)
        
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
            # 信号弹窗提醒
            if signal in ["🟢 进场信号", "🔴 出场信号"]:
                st.toast(f"{sym}：{signal}！", icon=signal[0])
    
    # 展示数据表格
    if market_data:
        df = pd.DataFrame(market_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        all_signals.extend(market_data)
    else:
        st.info(f"{market} 暂无可用数据（可能非交易时间/标的不支持）")

# 生成日报按钮
if st.button("📧 生成并发送今日日报"):
    with st.spinner("正在生成日报...（约1-2分钟）"):
        try:
            report = f"=== 全球市场日报 {datetime.now().strftime('%Y-%m-%d')} ===\n"
            report += f"初始资金：{INITIAL_CAPITAL} MYR | 单仓上限：{POSITION_LIMIT*100}%\n\n"
            for market, symbols in STOCK_POOL.items():
                report += f"--- {market} ---\n"
                for i, sym in enumerate(symbols):
                    if i % 5 == 0 and i > 0:
                        import time as t
                        t.sleep(12)
                    data = get_stock_data_alpha_vantage(sym)
                    if data:
                        sig = generate_signal(data)
                        report += f"{sym}: 现价{data['Close']:.2f} | {sig}\n"
            send_daily_report(report)
        except Exception as e:
            st.error(f"❌ 日报生成失败：{str(e)}")

st.divider()
st.caption(f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据源：Alpha Vantage | 标的总数：100只")
