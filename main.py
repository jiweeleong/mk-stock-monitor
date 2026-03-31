#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
马股双股票池 + 双策略监控报告
成长股池 → EMA10/27
短线股池 → EMA8/25
每日18:00发送邮件，买入信号绿色高亮
"""

import os
import sys
import time
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import yfinance as yf
import pandas as pd

# ------------------- 日志配置 -------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== 【1】成长股股票池 → EMA10/27 ====================
GROWTH_STOCKS = [
    "1155.KL", "1295.KL", "1023.KL", "5347.KL", "5225.KL",
    "8869.KL", "5819.KL", "4197.KL", "5211.KL", "6947.KL",
    "6033.KL", "3816.KL", "1066.KL", "4863.KL", "6012.KL",
    "6742.KL", "4707.KL", "1082.KL", "1961.KL", "5398.KL"
]

# ==================== 【2】短线股股票池 → EMA8/25 ====================
SHORT_STOCKS = [
    "FFB.KL", "KGB.KL", "GCB.KL", "DRB-HCOM.KL", "E&O.KL",
    "LSH.KL", "SSB8.KL", "ANCOMNY.KL", "PEKAT.KL", "ATECH.KL",
    "MFLOUR.KL", "DUFU.KL", "MHB.KL", "WCT.KL", "MAGMA.KL",
    "PARAGON.KL", "AVANGAAD.KL", "RGB.KL", "SAMCHEM.KL",
    "RANHILL.KL", "JPG.KL", "PTRANS.KL", "EDELTEQ.KL", "CHINHIN.KL",
    "BURSA.KL", "ITMAX.KL", "TOPGLOV.KL", "KOSSAN.KL", "MAHSING.KL",
    "BNASTRA.KL", "SCGBHD.KL", "CAPITALA.KL", "PECCA.KL", "SNS.KL",
    "KJTS.KL", "CYPARK.KL", "GLOTEC.KL", "UZMA.KL", "NOTION.KL",
    "SEALINK.KL", "SJC.KL"
]

# ==================== 策略参数 ====================
VOL_PERIOD = 20
VOL_MULTIPLE = 1.2

# ==================== 邮件配置 ====================
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

SCHEDULE_HOUR = 18
SCHEDULE_MINUTE = 0

# ==================== 策略判断函数 ====================
def analyze_growth(hist):
    """成长股 EMA10/27"""
    ema10 = hist['Close'].ewm(span=10, adjust=False).mean()
    ema27 = hist['Close'].ewm(span=27, adjust=False).mean()
    vol_ma = hist['Volume'].rolling(window=VOL_PERIOD).mean()
    if len(hist) < 60:
        return "数据不足", "无", "无"

    c_ema10 = ema10.iloc[-1]
    c_ema27 = ema27.iloc[-1]
    c_close = hist['Close'].iloc[-1]
    c_vol = hist['Volume'].iloc[-1]
    c_vol_ma = vol_ma.iloc[-1]

    trend = "多头" if c_ema10 > c_ema27 else "空头" if c_ema10 < c_ema27 else "盘整"
    buy = (c_ema10 > c_ema27) and (c_close > c_ema10) and (c_vol > c_vol_ma * VOL_MULTIPLE)
    sell = (c_ema10 < c_ema27) and (c_close < c_ema10)

    buy_signal = "成长买入" if buy else "无"
    sell_signal = "成长卖出" if sell else "无"
    return trend, buy_signal, sell_signal

def analyze_short(hist):
    """短线股 EMA8/25"""
    ema8 = hist['Close'].ewm(span=8, adjust=False).mean()
    ema25 = hist['Close'].ewm(span=25, adjust=False).mean()
    vol_ma = hist['Volume'].rolling(window=VOL_PERIOD).mean()
    if len(hist) < 60:
        return "数据不足", "无", "无"

    c_ema8 = ema8.iloc[-1]
    c_ema25 = ema25.iloc[-1]
    c_close = hist['Close'].iloc[-1]
    c_vol = hist['Volume'].iloc[-1]
    c_vol_ma = vol_ma.iloc[-1]

    trend = "多头" if c_ema8 > c_ema25 else "空头" if c_ema8 < c_ema25 else "盘整"
    buy = (c_ema8 > c_ema25) and (c_close > c_ema8) and (c_vol > c_vol_ma * VOL_MULTIPLE)
    sell = (c_ema8 < c_ema25) and (c_close < c_ema8)

    buy_signal = "短线买入" if buy else "无"
    sell_signal = "短线卖出" if sell else "无"
    return trend, buy_signal, sell_signal

# ==================== 获取单只股票信息 ====================
def get_stock(code, pool_type):
    try:
        ticker = yf.Ticker(code)
        hist = ticker.history(period="3mo")
        if hist.empty:
            return None

        # 名称 & 价格 & 涨跌幅
        name = ticker.info.get("shortName", code)
        close = round(hist['Close'].iloc[-1], 2)
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else hist['Close'].iloc[-1]
        change = round((close - prev) / prev * 100, 2)

        # 策略判断
        if pool_type == "growth":
            trend, buy, sell = analyze_growth(hist)
        else:
            trend, buy, sell = analyze_short(hist)

        return {
            "code": code,
            "name": name,
            "price": close,
            "change": change,
            "trend": trend,
            "buy": buy,
            "sell": sell,
            "pool": pool_type
        }
    except Exception as e:
        logger.warning(f"{code} 错误: {e}")
        return None

# ==================== 扫描全部 ====================
def scan():
    growth_list = []
    short_list = []

    logger.info("扫描成长股池...")
    for code in GROWTH_STOCKS:
        res = get_stock(code, "growth")
        if res:
            growth_list.append(res)

    logger.info("扫描短线股池...")
    for code in SHORT_STOCKS:
        res = get_stock(code, "short")
        if res:
            short_list.append(res)

    return growth_list, short_list

# ==================== 生成HTML报告 ====================
def render_table(title, data_list):
    html = f"<h3 style='color:#004080'>{title}</h3>"
    html += "<table border='1' cellpadding='6' cellspacing='0' width='100%'>"
    html += """
    <tr style='background:#f5f5f5'>
        <th>代码</th><th>名称</th><th>价格</th><th>涨跌幅(%)</th><th>趋势</th><th>买入信号</th><th>卖出信号</th>
    </tr>
    """
    for d in data_list:
        # 高亮：买入=浅绿，卖出=浅红
        bg = ""
        if d["buy"] != "无":
            bg = "style='background:#e6ffec'"
        elif d["sell"] != "无":
            bg = "style='background:#ffe6e6'"

        color = "green" if d["change"] >= 0 else "red"
        html += f"""
        <tr {bg}>
            <td>{d['code']}</td>
            <td>{d['name']}</td>
            <td>{d['price']}</td>
            <td style='color:{color}'>{d['change']}</td>
            <td>{d['trend']}</td>
            <td>{d['buy']}</td>
            <td>{d['sell']}</td>
        </tr>
        """
    html += "</table><br><br>"
    return html

def generate_html(growth, short):
    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>body {{font-family:Arial; line-height:1.6}}</style>
    </head>
    <body>
        <h2>马股收盘报告 {datetime.now().strftime('%Y-%m-%d %H:%M')}</h2>
        <p>✅ 绿色 = 买入信号</p>
        <p>❌ 浅红 = 卖出信号</p>
        <hr>
    """
    html += render_table("【成长股池 · EMA10/27】", growth)
    html += render_table("【短线股池 · EMA8/25】", short)
    html += "</body></html>"
    return html

# ==================== 发送邮件 ====================
def send_mail(html_content):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        logger.error("邮件环境变量未配置")
        return False

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = f"马股双策略收盘报告 {datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info("邮件发送成功")
        return True
    except Exception as e:
        logger.error(f"邮件失败: {e}")
        return False

# ==================== 主程序 ====================
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logger.info("立即执行...")
        g, s = scan()
        html = generate_html(g, s)
        send_mail(html)
        return

    logger.info(f"定时模式：每日 {SCHEDULE_HOUR}:{SCHEDULE_MINUTE} 执行")
    while True:
        now = datetime.now()
        if now.hour == SCHEDULE_HOUR and now.minute == SCHEDULE_MINUTE:
            g, s = scan()
            html = generate_html(g, s)
            send_mail(html)
            time.sleep(60)
        time.sleep(60)

if __name__ == "__main__":
    main()
