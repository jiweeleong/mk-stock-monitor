#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
马股 双策略合并监控
✅ 成长股 EMA 10/27
✅ 短线股 EMA 8/25
✅ 一起扫描 + 一起发邮件 + 高亮买入信号
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================= 股票池（你图片里的全部） =======================
MY_STOCKS = [
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

# ======================= 双策略参数 =======================
def check_growth_strategy(hist):
    # 成长股 EMA 10 / 27
    ema10 = hist['Close'].ewm(span=10, adjust=False).mean()
    ema27 = hist['Close'].ewm(span=27, adjust=False).mean()
    vol_ma = hist['Volume'].rolling(window=20).mean()
    if len(hist) < 60: return False, ""
    cnd1 = ema10.iloc[-1] > ema27.iloc[-1]
    cnd2 = hist['Close'].iloc[-1] > ema10.iloc[-1]
    cnd3 = hist['Volume'].iloc[-1] > vol_ma.iloc[-1] * 1.2
    return (cnd1 and cnd2 and cnd3), "成长10/27"

def check_short_strategy(hist):
    # 短线 EMA 8 / 25
    ema8 = hist['Close'].ewm(span=8, adjust=False).mean()
    ema25 = hist['Close'].ewm(span=25, adjust=False).mean()
    vol_ma = hist['Volume'].rolling(window=20).mean()
    if len(hist) < 60: return False, ""
    cnd1 = ema8.iloc[-1] > ema25.iloc[-1]
    cnd2 = hist['Close'].iloc[-1] > ema8.iloc[-1]
    cnd3 = hist['Volume'].iloc[-1] > vol_ma.iloc[-1] * 1.2
    return (cnd1 and cnd2 and cnd3), "短线8/25"

# ======================= 邮件配置 =======================
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

# ======================= 扫描 =======================
def scan():
    logger.info("开始双策略扫描...")
    result = []
    for code in MY_STOCKS:
        try:
            hist = yf.Ticker(code).history(period="6mo")
            if hist.empty: continue

            buy_growth, typ_growth = check_growth_strategy(hist)
            buy_short, typ_short = check_short_strategy(hist)
            buy = buy_growth or buy_short
            strategy = typ_growth if buy_growth else typ_short if buy_short else ""

            close = round(hist['Close'].iloc[-1], 2)
            name = yf.Ticker(code).info.get('shortName', code)
            result.append([code, name, close, buy, strategy])
            logger.info(f"{code} | {strategy} | 买入={buy}")
        except Exception as e:
            continue
    return pd.DataFrame(result, columns=["代码","名称","价格","买入信号","策略"])

# ======================= 报告 =======================
def send(df):
    html = "<h2>马股双策略买入信号</h2><table border='1' cellpadding='4'>"
    html += "<tr><th>代码</th><th>股票</th><th>价格</th><th>策略</th></tr>"
    for _, r in df.iterrows():
        color = "#90EE90" if r['买入信号'] else "white"
        html += f"<tr bgcolor='{color}'><td>{r['代码']}</td><td>{r['名称']}</td><td>{r['价格']}</td><td>{r['策略']}</td></tr>"
    html += "</table>"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = f"马股双策略买入信号 {datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info("邮件发送成功")
    except Exception as e:
        logger.error("邮件失败: %s", e)

if __name__ == "__main__":
    df = scan()
    send(df)
