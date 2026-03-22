#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
港股技术选股监控脚本
功能：
- 每日香港时间20:30自动运行一次
- 从yfinance获取60只港股的日线数据
- 根据均线、MACD、RSI、成交量等技术指标生成买入/卖出信号
- 发送邮件报告（仅使用Email）
- 适用于Replit环境，支持24小时运行

作者：AI助手
创建日期：2025-03-21
版本：1.0
"""

import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import time
import os
import logging
import pytz
from typing import Dict, List, Tuple

# ---------------------------- 配置区域 ----------------------------
# 邮件配置（请替换为您的实际邮箱信息）
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', 'your_email@gmail.com')       # 发件邮箱
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'your_app_password')      # 邮箱授权码（非登录密码）
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', 'recipient@example.com') # 收件邮箱
SMTP_SERVER = 'smtp.gmail.com'              # Gmail的SMTP服务器，如使用其他邮箱请修改
SMTP_PORT = 587

# 港股列表（去重后共59只，原列表有重复）
STOCK_LIST_RAW = [
    '00700.HK', '09988.HK', '03690.HK', '09618.HK', '09999.HK', '01810.HK', '01024.HK', '09626.HK', '09888.HK', '09961.HK',
    '09898.HK', '03888.HK', '00772.HK', '02400.HK', '00302.HK', '00005.HK', '01299.HK', '02318.HK', '00939.HK', '01396.HK',
    '03988.HK', '03968.HK', '00388.HK', '06030.HK', '02611.HK', '06837.HK', '02601.HK', '02628.HK', '01336.HK', '06060.HK',
    '00883.HK', '00700.HK', '02331.HK', '03690.HK', '00941.HK', '00001.HK', '00016.HK', '00101.HK', '00669.HK', '02020.HK',
    '01516.HK', '00014.HK', '00020.HK', '00017.HK', '00151.HK', '00023.HK', '00010.HK', '00011.HK', '00050.HK', '00012.HK',
    '00041.HK', '00024.HK', '00086.HK', '00027.HK', '00123.HK', '00071.HK', '00064.HK', '00056.HK', '00011.HK', '00015.HK'
]
# 去重并保持顺序
STOCKS = list(dict.fromkeys(STOCK_LIST_RAW))
print(f"股票总数：{len(STOCKS)}")

# 技术参数
MA_SHORT = 5      # 短期均线
MA_LONG = 20      # 长期均线
MA_60 = 60        # 60日均线
RSI_PERIOD = 14
VOL_MA = 5        # 成交量均线周期

# 信号阈值
BUY_THRESHOLD = 3   # 买入至少满足几条
SELL_THRESHOLD = 2  # 卖出至少满足几条

# 香港时区
HK_TZ = pytz.timezone('Asia/Hong_Kong')

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------- 辅助函数 ----------------------------
def get_hk_now():
    """返回当前香港时间"""
    return datetime.now(HK_TZ)

def is_time_to_run(last_run_date=None):
    """
    判断是否到达20:30并且今天还没有运行过。
    返回 (是否需要运行, 今天日期)
    """
    now = get_hk_now()
    today = now.date()
    target_time = now.replace(hour=20, minute=30, second=0, microsecond=0)
    # 如果当前时间在20:30之后，并且今天还没有运行过
    if now >= target_time and (last_run_date is None or last_run_date < today):
        return True, today
    else:
        return False, None

def convert_hk_code(code: str) -> str:
    """
    将港股代码转换为yfinance可识别的格式。
    例如 00700.HK -> 0700.HK （去掉前导0）
    """
    if code.endswith('.HK'):
        num_part = code.split('.')[0].lstrip('0')
        # 如果去掉0后为空（如00001.HK -> 1.HK），则保留至少一位数字
        if num_part == '':
            num_part = '0'
        return f"{num_part}.HK"
    return code

def get_stock_data(code: str, period='3mo') -> pd.DataFrame:
    """
    从yfinance获取股票日线数据，返回DataFrame。
    数据包含：Open, High, Low, Close, Volume
    """
    try:
        ticker = yf.Ticker(convert_hk_code(code))
        df = ticker.history(period=period)
        if df.empty:
            logger.warning(f"{code} 无数据")
            return None
        # 确保索引为日期
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception as e:
        logger.error(f"获取{code}数据失败: {e}")
        return None

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算技术指标：均线、MACD、RSI、成交量均量
    返回增加了指标的DataFrame
    """
    if df is None or len(df) < MA_LONG:
        return None

    # 均线
    df['MA5'] = df['Close'].rolling(window=MA_SHORT).mean()
    df['MA20'] = df['Close'].rolling(window=MA_LONG).mean()
    df['MA60'] = df['Close'].rolling(window=MA_60).mean()

    # 成交量均量
    df['VOL_MA5'] = df['Volume'].rolling(window=VOL_MA).mean()

    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']

    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=RSI_PERIOD).mean()
    avg_loss = loss.rolling(window=RSI_PERIOD).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    return df

def check_buy_signals(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    检查最新交易日买入信号
    返回 (是否满足买入条件, 触发的信号列表)
    """
    if df is None or len(df) < MA_LONG:
        return False, []

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None
    signals = []

    # 1. 5日均线上穿20日均线形成金叉
    if prev is not None and last['MA5'] > last['MA20'] and prev['MA5'] <= prev['MA20']:
        signals.append("5日线上穿20日线（金叉）")

    # 2. MACD金叉，柱由绿转红
    if prev is not None and last['MACD'] > last['Signal'] and prev['MACD'] <= prev['Signal']:
        signals.append("MACD金叉，柱转红")

    # 3. RSI(14)从低于30回升到40以上
    if prev is not None and last['RSI'] > 40 and prev['RSI'] < 30:
        signals.append("RSI从30以下回升至40以上")

    # 4. 成交量大于5日均量1.5倍，放量上涨
    if last['Volume'] > last['VOL_MA5'] * 1.5 and last['Close'] > last['Open']:
        signals.append("放量上涨（量>均量1.5倍，收盘>开盘）")

    # 5. 股价站稳60日均线之上
    if last['Close'] > last['MA60']:
        signals.append("股价站稳60日均线之上")

    return len(signals) >= BUY_THRESHOLD, signals

def check_sell_signals(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    检查最新交易日卖出信号
    返回 (是否满足卖出条件, 触发的信号列表)
    """
    if df is None or len(df) < MA_LONG:
        return False, []

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None
    signals = []

    # 1. 5日均线下穿20日均线形成死叉
    if prev is not None and last['MA5'] < last['MA20'] and prev['MA5'] >= prev['MA20']:
        signals.append("5日线下穿20日线（死叉）")

    # 2. MACD死叉，柱由红转绿
    if prev is not None and last['MACD'] < last['Signal'] and prev['MACD'] >= prev['Signal']:
        signals.append("MACD死叉，柱转绿")

    # 3. RSI(14)从高于70回落至50以下
    if prev is not None and last['RSI'] < 50 and prev['RSI'] > 70:
        signals.append("RSI从70以上回落至50以下")

    # 4. 放量下跌，成交量大于5日均量2倍
    if last['Volume'] > last['VOL_MA5'] * 2 and last['Close'] < last['Open']:
        signals.append("放量下跌（量>均量2倍，收盘<开盘）")

    # 5. 股价跌破20日均线且走弱
    if last['Close'] < last['MA20']:
        signals.append("股价跌破20日均线")

    return len(signals) >= SELL_THRESHOLD, signals

def generate_report(buy_stocks: List[Tuple[str, float, List[str]]],
                    sell_stocks: List[Tuple[str, float, List[str]]],
                    date: str) -> str:
    """
    生成邮件正文HTML
    """
    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; }}
            h2 {{ color: #2c3e50; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .buy {{ background-color: #d4edda; }}
            .sell {{ background-color: #f8d7da; }}
        </style>
    </head>
    <body>
        <h2>港股技术选股日报 - {date}</h2>
        <h3>📈 买入信号股票（满足{BUY_THRESHOLD}条及以上）</h3>
    """
    if buy_stocks:
        html += """
        <table>
            <tr><th>股票代码</th><th>当前价格</th><th>触发信号</th></tr>
        """
        for code, price, signals in buy_stocks:
            signal_str = "<br>".join(signals)
            html += f"<tr><td>{code}</td><td>{price:.2f} HKD</td><td>{signal_str}</td></tr>"
        html += "</table>"
    else:
        html += "<p>暂无符合买入条件的股票。</p>"

    html += "<h3>📉 卖出信号股票（满足{}条及以上）</h3>".format(SELL_THRESHOLD)
    if sell_stocks:
        html += """
        <table>
            <tr><th>股票代码</th><th>当前价格</th><th>触发信号</th></tr>
        """
        for code, price, signals in sell_stocks:
            signal_str = "<br>".join(signals)
            html += f"<tr><td>{code}</td><td>{price:.2f} HKD</td><td>{signal_str}</td></tr>"
        html += "</table>"
    else:
        html += "<p>暂无符合卖出条件的股票。</p>"

    html += "<p><em>注：本报告仅基于技术指标自动生成，不构成投资建议。</em></p>"
    html += "</body></html>"
    return html

def send_email(subject: str, html_content: str):
    """
    发送邮件
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECIPIENT

        part = MIMEText(html_content, 'html')
        msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info("邮件发送成功")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")

def run_daily_analysis():
    """
    执行每日分析：遍历所有股票，计算信号，生成报告并发送邮件。
    """
    logger.info("开始每日分析...")
    buy_list = []
    sell_list = []

    for stock in STOCKS:
        logger.info(f"处理 {stock}")
        df = get_stock_data(stock, period='3mo')
        if df is None:
            continue
        df = compute_indicators(df)
        if df is None:
            continue
        # 获取最新收盘价
        latest_price = df['Close'].iloc[-1]

        # 检查买入信号
        buy_flag, buy_signals = check_buy_signals(df)
        if buy_flag:
            buy_list.append((stock, latest_price, buy_signals))
            logger.info(f"{stock} 触发买入信号")

        # 检查卖出信号
        sell_flag, sell_signals = check_sell_signals(df)
        if sell_flag:
            sell_list.append((stock, latest_price, sell_signals))
            logger.info(f"{stock} 触发卖出信号")

    # 生成报告并发送
    today_str = get_hk_now().strftime('%Y-%m-%d')
    subject = f"【港股技术选股日报】{today_str}"
    html = generate_report(buy_list, sell_list, today_str)
    send_email(subject, html)
    logger.info("每日分析完成")

def main():
    """
    主循环：每60秒检查一次是否到达20:30，并执行当日任务。
    """
    last_run_date = None
    logger.info("监控程序启动，等待每日20:30执行...")

    while True:
        try:
            need_run, today = is_time_to_run(last_run_date)
            if need_run:
                logger.info(f"到达执行时间 {today} 20:30，开始运行...")
                run_daily_analysis()
                last_run_date = today
                logger.info(f"今日任务完成，下次运行时间：明日20:30")
            # 每60秒检查一次
            time.sleep(60)
        except Exception as e:
            logger.error(f"主循环异常: {e}")
            time.sleep(60)

if __name__ == "__main__":
    # 启动前测试邮件配置（可选）
    # 如果环境变量未设置，提醒用户
    if EMAIL_SENDER == 'your_email@gmail.com' or EMAIL_PASSWORD == 'your_app_password' or EMAIL_RECIPIENT == 'recipient@example.com':
        logger.warning("请先正确设置邮件环境变量（EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT）！")
    main()