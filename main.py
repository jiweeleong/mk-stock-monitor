#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票监控程序
- 每天16:00执行一次监控，发送邮件报告
- 使用 --now 参数立即执行一次
- 邮件配置：优先读取环境变量，否则使用内置默认值
- 股票列表：优先读取 stocks.txt，否则使用内置50只港股
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
import numpy as np
import pytz

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 配置区域 ====================
# 1. 股票代码文件路径（每行一个股票代码，如 00700.HK, AAPL 等）
STOCKS_FILE = "stocks.txt"

# 2. 默认股票列表（50只港股）
DEFAULT_STOCKS = [
    "00001.HK", "00002.HK", "00003.HK", "00005.HK", "00006.HK",   # 长和、中电、香港中华煤气、汇丰、电能实业
    "00011.HK", "00016.HK", "00019.HK", "00027.HK", "00066.HK",   # 恒生、新地、太古A、银河娱乐、港铁
    "00101.HK", "00175.HK", "00241.HK", "00267.HK", "00288.HK",   # 恒隆地产、吉利汽车、阿里健康、中信股份、万洲国际
    "00316.HK", "00322.HK", "00386.HK", "00388.HK", "00669.HK",   # 东方海外、康师傅、中石化、港交所、创科实业
    "00688.HK", "00700.HK", "00762.HK", "00823.HK", "00857.HK",   # 中海油、腾讯、中国电信、领展、中石油
    "00883.HK", "00939.HK", "00941.HK", "00981.HK", "00992.HK",   # 中海油、建设银行、中国移动、中芯国际、联想
    "01024.HK", "01088.HK", "01109.HK", "01113.HK", "01211.HK",   # 快手、中国神华、华润置地、长实集团、比亚迪
    "01299.HK", "01398.HK", "01810.HK", "01876.HK", "01928.HK",   # 友邦保险、工商银行、小米、百威亚太、金沙中国
    "01997.HK", "02018.HK", "02020.HK", "02269.HK", "02318.HK",   # 九龙仓置业、瑞声科技、安踏体育、药明生物、中国平安
    "02331.HK", "02382.HK", "02688.HK", "02888.HK", "03328.HK",   # 李宁、舜宇光学、新奥能源、渣打集团、交通银行
]

# 3. 邮件配置（优先使用环境变量，否则使用硬编码默认值）
#   请将以下默认值替换为您的实际邮箱信息
DEFAULT_EMAIL_SENDER = "jiweeleong@gmail.com"
DEFAULT_EMAIL_PASSWORD = "zjiktdqlomznuqxl"   # 您的16位应用专用密码
DEFAULT_EMAIL_RECIPIENT = "jiweeleong@gmail.com"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER", DEFAULT_EMAIL_SENDER)
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", DEFAULT_EMAIL_PASSWORD)
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", DEFAULT_EMAIL_RECIPIENT)

# 4. 定时执行时间（24小时制）
SCHEDULE_HOUR = 16
SCHEDULE_MINUTE = 0

# ==================== 辅助函数 ====================
def load_stocks():
    """加载股票代码列表"""
    stocks = []
    if os.path.exists(STOCKS_FILE):
        with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                code = line.strip()
                if code and not code.startswith('#'):
                    stocks.append(code)
        if stocks:
            logger.info(f"从 {STOCKS_FILE} 加载了 {len(stocks)} 只股票")
            return stocks
    logger.warning(f"未找到 {STOCKS_FILE}，使用默认港股列表")
    return DEFAULT_STOCKS

def get_stock_data(stock_codes):
    """获取股票数据，返回 DataFrame"""
    data = []
    for code in stock_codes:
        try:
            ticker = yf.Ticker(code)
            # 获取最新交易日数据
            hist = ticker.history(period="1d")
            if hist.empty:
                logger.warning(f"{code} 无数据")
                continue
            last = hist.iloc[-1]
            price = last['Close']
            prev_close = last['Open']  # 实际应为前一日收盘，这里简化
            # 计算涨跌幅（相对于前一日收盘）
            change_pct = (price - prev_close) / prev_close * 100 if prev_close else 0
            data.append({
                'code': code,
                'price': round(price, 2),
                'change_pct': round(change_pct, 2),
                'volume': int(last['Volume']),
                'date': last.name.strftime('%Y-%m-%d')
            })
        except Exception as e:
            logger.error(f"获取 {code} 数据失败: {e}")
    return pd.DataFrame(data)

def generate_report(df):
    """生成邮件报告内容（HTML 格式）"""
    if df.empty:
        return "<p>未获取到任何股票数据。</p>"
    html = """
    <html>
    <head>
        <style>
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }
            th { background-color: #f2f2f2; text-align: center; }
            .positive { color: green; }
            .negative { color: red; }
        </style>
    </head>
    <body>
        <h3>股票监控报告 - {date}</h3>
        <table>
            <tr><th>代码</th><th>最新价</th><th>涨跌幅(%)</th><th>成交量</th><th>日期</th></tr>
    """.format(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    for _, row in df.iterrows():
        change_class = "positive" if row['change_pct'] >= 0 else "negative"
        html += f"""
            <tr>
                <td>{row['code']}</td>
                <td>{row['price']}</td>
                <td class="{change_class}">{row['change_pct']}</td>
                <td>{row['volume']:,}</td>
                <td>{row['date']}</td>
            </tr>
        """
    html += "</table></body></html>"
    return html

def send_email(subject, content_html):
    """发送邮件"""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        logger.error("邮件配置不完整，无法发送邮件")
        return False

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(content_html, 'html', 'utf-8'))

    try:
        # 使用 Gmail SMTP 服务器，若使用其他邮箱请修改
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

def monitor():
    """执行监控任务：获取数据、生成报告、发送邮件"""
    logger.info("开始执行监控任务...")
    stocks = load_stocks()
    if not stocks:
        logger.error("股票列表为空，无法监控")
        return
    logger.info(f"共 {len(stocks)} 只股票，开始获取数据...")
    df = get_stock_data(stocks)
    if df.empty:
        logger.warning("未获取到任何数据")
        return
    # 生成报告
    report = generate_report(df)
    # 发送邮件
    subject = f"股票监控报告 - {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject, report)
    logger.info("监控任务完成")

def main():
    """主函数，处理参数并启动"""
    if len(sys.argv) > 1 and sys.argv[1] == '--now':
        logger.info("立即执行模式启动...")
        monitor()
        return

    logger.info(f"定时监控模式启动，将在每天 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} 执行")
    while True:
        now = datetime.now()
        if now.hour == SCHEDULE_HOUR and now.minute == SCHEDULE_MINUTE:
            logger.info(f"定时时间到，开始执行...")
            monitor()
            # 等待一分钟，避免同一分钟内重复执行
            time.sleep(60)
        time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    main()
