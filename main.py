#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
马股双股票池 + 双策略监控（最终版）
✅ 成长股池 → EMA10/27
✅ 短线股池 → EMA8/25
✅ 所有股票均使用正确KLSE数字代码
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== 【1】成长股池（你给的前两张图）→ EMA10/27 ====================
GROWTH_STOCKS = [
    "5272.KL", "7167.KL", "0182.KL", "5190.KL", "5273.KL",
    "1818.KL", "0183.KL", "7113.KL", "7153.KL", "8583.KL",
    "5100.KL", "5111.KL", "5099.KL", "5279.KL", "0185.KL",
    "0184.KL", "5184.KL", "5198.KL", "7210.KL", "0083.KL",
    "5141.KL", "5275.KL"
]

# ==================== 【2】短线股池（你最新两张图）→ EMA8/25 ====================
SHORT_STOCKS = [
    "5306.KL", "0151.KL", "5102.KL", "1619.KL", "3417.KL",
    "0125.KL", "0157.KL", "4757.KL", "0156.KL", "0154.KL",
    "3662.KL", "7233.KL", "5264.KL", "9676.KL", "5265.KL",
    "9741.KL", "0145.KL", "7013.KL", "4703.KL"
]

# ==================== 策略参数 ====================
VOL_PERIOD = 20
VOL_MULTIPLE = 1.2  # 温和放量倍数

# ==================== 邮件配置 ====================
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

SCHEDULE_HOUR = 18
SCHEDULE_MINUTE = 0

# ==================== 策略判断函数 ====================
def analyze_growth(hist):
    """成长股 EMA10/27 策略"""
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

    trend = "多头" if c_ema10 > c_ema27 else "空头"
    buy = (c_ema10 > c_ema27) and (c_close > c_ema10) and (c_vol > c_vol_ma * VOL_MULTIPLE)
    sell = (c_ema10 < c_ema27) and (c_close < c_ema10)

    return trend, "成长买入" if buy else "无", "成长卖出" if sell else "无"

def analyze_short(hist):
    """短线股 EMA8/25 策略"""
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

    trend = "多头" if c_ema8 > c_ema25 else "空头"
    buy = (c_ema8 > c_ema25) and (c_close > c_ema8) and (c_vol > c_vol_ma * VOL_MULTIPLE)
    sell = (c_ema8 < c_ema25) and (c_close < c_ema8)

    return trend, "短线买入" if buy else "无", "短线卖出" if sell else "无"

# ==================== 获取单只股票信息 ====================
def get_stock(code, pool_type):
    try:
        ticker = yf.Ticker(code)
        hist = ticker.history(period="3mo")
        if hist.empty:
            return None

        # 基础数据
        name = ticker.info.get("shortName", code)
        close = round(hist['Close'].iloc[-1], 2)
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else hist['Close'].iloc[-1]
        change = round((close - prev) / prev * 100, 2)

        # 策略分析
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
            "sell": sell
        }
    except Exception as e:
        logger.warning(f"{code} 获取失败: {e}")
        return None

# ==================== 扫描全部股票 ====================
def scan():
    logger.info("正在扫描成长股池...")
    growth_list = []
    for code in GROWTH_STOCKS:
        res = get_stock(code, "growth")
        if res:
            growth_list.append(res)

    logger.info("正在扫描短线股池...")
    short_list = []
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
        # 高亮规则：买入=浅绿，卖出=浅红
        bg_color = ""
        if d["buy"] != "无":
            bg_color = "style='background-color:#e6ffec'"
        elif d["sell"] != "无":
            bg_color = "style='background-color:#ffe6e6'"

        change_color = "green" if d["change"] >= 0 else "red"
        html += f"""
        <tr {bg_color}>
            <td>{d['code']}</td>
            <td>{d['name']}</td>
            <td>{d['price']}</td>
            <td style='color:{change_color}'>{d['change']}</td>
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
        <p>✅ 绿色背景 = 买入信号</p>
        <p>❌ 红色背景 = 卖出信号</p>
        <hr>
    """
    html += render_table("【成长股池 · EMA10/27】", growth)
    html += render_table("【短线股池 · EMA8/25】", short)
    html += "</body></html>"
    return html

# ==================== 发送邮件 ====================
def send_mail(html_content):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        logger.error("邮件环境变量未配置完整")
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
        logger.error(f"邮件发送失败: {e}")
        return False

# ==================== 主程序 ====================
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logger.info("立即执行扫描...")
        growth_data, short_data = scan()
        html = generate_html(growth_data, short_data)
        send_mail(html)
        return

    logger.info(f"定时模式：每日 {SCHEDULE_HOUR}:{SCHEDULE_MINUTE} 自动执行")
    while True:
        now = datetime.now()
        if now.hour == SCHEDULE_HOUR and now.minute == SCHEDULE_MINUTE:
            growth_data, short_data = scan()
            html = generate_html(growth_data, short_data)
            send_mail(html)
            time.sleep(60)
        time.sleep(60)

if __name__ == "__main__":
    main()
