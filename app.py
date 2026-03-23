import streamlit as st
import pandas as pd
import requests
import time

# ---------------------- 页面基础设置 ----------------------
st.set_page_config(
    page_title="我的股票监控面板",  # 页面标题
    page_icon="📈",  # 图标（可选）
    layout="wide"  # 宽屏布局
)

# ---------------------- 侧边栏配置 ----------------------
st.sidebar.title("📊 股票监控设置")
# 示例：让用户输入要监控的股票代码
stock_codes = st.sidebar.text_input(
    "输入要监控的股票代码（逗号分隔）",
    value="600000,000001,300059"  # 默认值
)
# 示例：监控频率选择
check_frequency = st.sidebar.selectbox(
    "监控频率",
    options=["实时", "5分钟", "30分钟", "1小时"],
    index=1
)

# ---------------------- 核心股票监控逻辑 ----------------------
def get_stock_data(codes):
    """
    替换成你自己的股票数据获取逻辑
    这里是示例，返回模拟数据
    """
    # 拆分股票代码
    code_list = [code.strip() for code in codes.split(",") if code.strip()]
    
    # 模拟股票数据（你需要替换成真实的接口调用）
    data = []
    for code in code_list:
        data.append({
            "股票代码": code,
            "当前价格": round(10 + (hash(code) % 100) / 10, 2),  # 模拟价格
            "涨跌幅(%)": round((hash(code) % 20 - 10) / 10, 2),  # 模拟涨跌幅
            "成交量": f"{hash(code) % 1000}万手",
            "更新时间": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return pd.DataFrame(data)

# ---------------------- 主页面展示 ----------------------
st.title("📈 我的股票监控面板")
st.markdown("---")  # 分隔线

# 获取并展示股票数据
if stock_codes:
    with st.spinner("正在获取股票数据..."):
        stock_df = get_stock_data(stock_codes)
        
        # 展示数据表格
        st.subheader("实时股票数据")
        st.dataframe(
            stock_df,
            use_container_width=True,  # 自适应宽度
            hide_index=True  # 隐藏索引列
        )
        
        # 高亮显示涨跌幅异常的股票（示例）
        st.subheader("⚠️ 异动提醒")
        abnormal_stocks = stock_df[(stock_df["涨跌幅(%)"] > 5) | (stock_df["涨跌幅(%)"] < -5)]
        if not abnormal_stocks.empty:
            st.error("发现涨跌幅超过5%的股票：")
            st.dataframe(abnormal_stocks, use_container_width=True, hide_index=True)
        else:
            st.success("暂无异常波动股票")
else:
    st.warning("请在侧边栏输入要监控的股票代码！")

# 显示最后更新时间
st.markdown(f"> 最后更新时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
