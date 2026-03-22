#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票监控程序（港股+马股精选版）
- 每天18:00执行一次监控，发送邮件报告
- 使用 --now 参数立即执行一次
- 趋势分析：上升/下跌/盘整，并检测趋势转换
- 趋势强度（MA5-MA20差距比例）并按实际数值降序排列（上升在前，下跌在后）
- 包含股票名称，移除成交量列和日期列，趋势转换行高亮
- 默认监控50只港股 + 50只马股（已验证有效代码）
- 可通过 stocks.txt 自定义股票列表
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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 配置区域 ====================
STOCKS_FILE = "stocks.txt"  # 可选，若存在则优先使用

# 精选港股 50 只（已验证有效）
HK_STOCKS = [
    "0001.HK", "0002.HK", "0003.HK", "0005.HK", "0006.HK",
    "0012.HK", "0016.HK", "0019.HK", "0027.HK", "0066.HK",
    "0101.HK", "0175.HK", "0241.HK", "0267.HK", "0288.HK",
    "0316.HK", "0322.HK", "0386.HK", "0388.HK", "0669.HK",
    "0688.HK", "0700.HK", "0762.HK", "0823.HK", "0857.HK",
    "0883.HK", "0939.HK", "0941.HK", "0981.HK", "0992.HK",
    "1024.HK", "1088.HK", "1109.HK", "1113.HK", "1211.HK",
    "1299.HK", "1398.HK", "1810.HK", "1876.HK", "1928.HK",
    "1997.HK", "2018.HK", "2020.HK", "2269.HK", "2318.HK",
    "2331.HK", "2382.HK", "2688.HK", "2888.HK", "3328.HK"
]

# 精选马股 50 只（已验证有效）
MY_STOCKS = [
    "1155.KL", "1295.KL", "1023.KL", "5347.KL", "5225.KL",
    "8869.KL", "5819.KL", "4197.KL", "5211.KL", "6947.KL",
    "6033.KL", "3816.KL", "1066.KL", "4863.KL", "6012.KL",
    "6742.KL", "4707.KL", "1082.KL", "1961.KL", "5398.KL",
    "4677.KL", "2445.KL", "1015.KL", "5079.KL", "6888.KL",
    "5681.KL", "5249.KL", "2089.KL", "5296.KL", "4065.KL",
    "7084.KL", "5227.KL", "5878.KL", "3794.KL", "4715.KL",
    "3182.KL", "5031.KL", "5288.KL", "7277.KL", "3336.KL",
    "0166.KL", "7204.KL", "5247.KL", "5145.KL", "4162.KL",
    "5099.KL", "5138.KL", "5140.KL", "5183.KL", "5326.KL"
]

DEFAULT_STOCKS = HK_STOCKS + MY_STOCKS

# 邮件配置（优先使用环境变量，否则使用硬编码默认值）
DEFAULT_EMAIL_SENDER = "jiweeleong@gmail.com"
DEFAULT_EMAIL_PASSWORD = "zjiktdqlomznuqxl"   # 您的16位应用专用密码
DEFAULT_EMAIL_RECIPIENT = "jiweeleong@gmail.com"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER", DEFAULT_EMAIL_SENDER)
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", DEFAULT_EMAIL_PASSWORD)
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", DEFAULT_EMAIL_RECIPIENT)

# 定时执行时间（下午6点）
SCHEDULE_HOUR = 18
SCHEDULE_MINUTE = 0

# ==================== 辅助函数 ====================
def load_stocks():
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
    logger.warning(f"未找到 {STOCKS_FILE}，使用默认港股+马股列表")
    return DEFAULT_STOCKS

def get_stock_data(stock_codes, period="1mo"):
    data = []
    total = len(stock_codes)
    for idx, code in enumerate(stock_codes, 1):
        try:
            logger.info(f"获取 {code} ({idx}/{total}) ...")
            ticker = yf.Ticker(code)
            hist = ticker.history(period=period)
            if hist.empty:
                logger.warning(f"{code} 无数据")
                continue

            # 获取股票名称
            try:
                info = ticker.info
                name = info.get('longName') or info.get('shortName') or code
            except Exception:
                name = code

            hist['MA5'] = hist['Close'].rolling(window=5).mean()
            hist['MA20'] = hist['Close'].rolling(window=20).mean()

            latest = hist.iloc[-1]
            ma5 = latest['MA5']
            ma20 = latest['MA20']
            if pd.notna(ma5) and pd.notna(ma20):
                diff_pct = (ma5 - ma20) / ma20 * 100
                if ma5 > ma20:
                    trend = '上升'
                elif ma5 < ma20:
                    trend = '下跌'
                else:
                    trend = '盘整'
            else:
                diff_pct = None
                trend = '数据不足'

            # 趋势转换
            if len(hist) >= 2:
                prev = hist.iloc[-2]
                prev_ma5 = prev['MA5']
                prev_ma20 = prev['MA20']
                if pd.notna(prev_ma5) and pd.notna(prev_ma20):
                    prev_trend = '上升' if prev_ma5 > prev_ma20 else ('下跌' if prev_ma5 < prev_ma20 else '盘整')
                else:
                    prev_trend = '数据不足'
                trend_change = (trend != prev_trend) and (trend != '数据不足') and (prev_trend != '数据不足')
                prev_close = prev['Close']
            else:
                trend_change = False
                prev_close = latest['Open'] if 'Open' in latest else latest['Close']

            change_pct = (latest['Close'] - prev_close) / prev_close * 100 if prev_close else 0

            data.append({
                'code': code,
                'name': name,
                'price': round(latest['Close'], 2),
                'change_pct': round(change_pct, 2),
                'trend': trend,
                'trend_change': '是' if trend_change else '否',
                'ma_diff_pct': round(diff_pct, 2) if diff_pct is not None else 'N/A'
            })
        except Exception as e:
            logger.error(f"获取 {code} 数据失败: {e}")
    return pd.DataFrame(data)

def generate_report(df):
    if df.empty:
        return "<p>未获取到任何股票数据。</p>"

    html = f"""
    <html>
    <head>
        <style>
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
            th {{ background-color: #f2f2f2; text-align: center; }}
            .positive {{ color: green; }}
            .negative {{ color: red; }}
            .trend-change {{ background-color: #ffe6e6; }}
            .trend-up {{ color: green; font-weight: bold; }}
            .trend-down {{ color: red; font-weight: bold; }}
            .trend-consolidation {{ color: gray; }}
            .strength-positive {{ color: green; }}
            .strength-negative {{ color: red; }}
        </style>
    </head>
    <body>
        <h3>股票监控报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h3>
        <p>说明：趋势基于5日均线与20日均线的关系（上升：MA5>MA20，下跌：MA5<MA20，盘整：其他）。趋势强度 = (MA5-MA20)/MA20×100%。趋势转换表示今日趋势与昨日不同。</p>
        <p><strong>股票已按趋势强度实际数值降序排列（上升趋势在前，下跌趋势在后）。</strong></p>
         <table>
             <tr>
                <th>代码</th><th>股票名称</th><th>最新价</th><th>涨跌幅(%)</th><th>当前趋势</th><th>趋势强度(%)</th><th>趋势转换</th>
             </tr>
    """

    for _, row in df.iterrows():
        change_class = "positive" if row['change_pct'] >= 0 else "negative"
        trend_class = {
            "上升": "trend-up",
            "下跌": "trend-down",
            "盘整": "trend-consolidation",
            "数据不足": ""
        }.get(row['trend'], "")
        strength_val = row['ma_diff_pct']
        strength_class = ""
        if isinstance(strength_val, (int, float)):
            strength_class = "strength-positive" if strength_val > 0 else ("strength-negative" if strength_val < 0 else "")
        row_class = "trend-change" if row['trend_change'] == "是" else ""

        html += f"""
            <tr class="{row_class}">
                <td>{row['code']}</td>
                <td style="text-align:left">{row['name']}</td>
                <td>{row['price']}</td>
                <td class="{change_class}">{row['change_pct']}</td>
                <td class="{trend_class}">{row['trend']}</td>
                <td class="{strength_class}">{strength_val}</td>
                <td>{row['trend_change']}</td>
            </tr>
        """
    html += " </table></body></html>"
    return html

def send_email(subject, content_html):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        logger.error("邮件配置不完整，无法发送邮件")
        return False

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(content_html, 'html', 'utf-8'))

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

def monitor():
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

    # 按趋势强度实际数值降序排列（正值在上，负值在下）
    df['sort_key'] = pd.to_numeric(df['ma_diff_pct'], errors='coerce')
    df = df.sort_values(by='sort_key', ascending=False, na_position='last')
    df = df.drop(columns=['sort_key'])

    report = generate_report(df)
    subject = f"股票监控报告 - {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject, report)
    logger.info("监控任务完成")

def main():
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
            time.sleep(60)
        time.sleep(60)

if __name__ == "__main__":
    main()
