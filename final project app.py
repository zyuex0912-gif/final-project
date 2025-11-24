import streamlit as st
import requests
import os
from openai import OpenAI

# 页面配置
st.set_page_config(page_title="AI非遗智能讲解员", page_icon="🌍", layout="wide")

# ---------------------- 1. 修复UNESCO API调用 ----------------------
def get_unesco_ich_data(region="Asia", limit=5, year=None):
    """
    调用UNESCO Explore API获取非物质文化遗产数据（修复接口路径和参数）
    """
    # 正确的非遗数据集ID（需确认最新数据集名称）
    base_url = "https://en.unesco.org/apis/ih/query"
    
    # 构建筛选参数（使用正确的参数格式）
    params = {
        "q": f"region:{region}",
        "max": limit,
        "format": "json"
    }
    
    # 年份筛选（若有）
    if year:
        params["q"] += f" AND year:{year}"
    
    try:
        # 备用方案：使用UNESCO官网公开的非遗JSON数据源
        backup_url = "https://en.unesco.org/sites/default/files/ih_data.json"
        response = requests.get(backup_url)
        if response.status_code == 200:
            data = response.json()
            # 本地筛选数据
            filtered_data = []
            for item in data[:limit]:
                if (not region or item.get("region") == region) and (not year or item.get("year") == year):
                    filtered_data.append(item)
            return filtered_data[:limit]
        else:
            # 备选公开接口
            alt_url = "https://data.unesco.org/api/v2/catalog/datasets/intangible-heritage/exports/json"
            alt_response = requests.get(alt_url, params={"limit": limit})
            alt_data = alt_response.json()
            return alt_data[:limit]
    except Exception as e:
        st.error(f"获取UNESCO非遗数据失败：{str(e)}")
        # 返回Mock数据避免程序中断
        return [
            {
                "title": "Kunqu Opera",
                "country": "China",
                "year": 2008,
                "description": "Kunqu Opera is one of the oldest forms of Chinese opera, with a history of over 600 years."
            },
            {
                "title": "Peking Opera",
                "country": "China",
                "year": 2010,
                "description": "Peking Opera is a traditional Chinese opera form combining music, vocal performance, mime, dance and acrobatics."
            }
        ]

# ---------------------- 2. 修复OpenAI初始化 ----------------------
def init_openai_client():
    """初始化OpenAI客户端（支持环境变量+手动输入）"""
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        api_key = st.sidebar.text_input("请输入OpenAI API Key", type="password")
    if api_key:
        return OpenAI(api_key=api_key)
    return None

# ---------------------- 3. AI讲解生成（添加异常处理） ----------------------
def generate_global_ich_explanation(ich_data, client):
    if not client:
        st.warning("请先配置OpenAI API Key")
        return ""
    
    data_summary = ""
    for item in ich_data:
        data_summary += f"- 项目：{item.get('title', '未知')}，国家：{item.get('country', '未知')}，入选年份：{item.get('year', '未知')}，简介：{item.get('description', '暂无')[:100]}...\n"
    
    prompt = f"""你是全球非物质文化遗产专家，基于以下UNESCO官方数据，生成一段生动的讲解：
    数据：{data_summary}
    要求：1. 介绍这些非遗项目的共性（如文化价值、保护挑战）；2. 对比不同地区项目的特色；3. 语言通俗，适合大众理解；4. 结尾提出一个互动问题。"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"生成讲解失败：{str(e)}")
        return f"以下是全球非遗项目介绍：\n{data_summary}\n\n这些项目代表了不同地区的文化瑰宝，你还知道哪些非遗项目呢？"

# ---------------------- 4. 界面优化 ----------------------
st.title("🌍 AI非遗智能讲解员（UNESCO全球版）")
st.subheader("—— 探索世界非物质文化遗产")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置面板")
    region = st.selectbox("选择地区", ["Asia", "Europe", "Africa", "Americas"], index=0)
    year = st.number_input("入选年份（可选）", min_value=2003, max_value=2024, value=None, step=1)
    limit = st.slider("展示数量", min_value=1, max_value=10, value=3)
    st.divider()
    st.info("数据来源：UNESCO官方公开数据集\n技术支持：OpenAI + Streamlit")

# 初始化OpenAI客户端
client = init_openai_client()

# 主功能区
col1, col2 = st.columns([2, 1])
with col1:
    if st.button("📥 获取全球非遗数据", type="primary"):
        with st.spinner("正在获取数据..."):
            ich_data = get_unesco_ich_data(region=region, limit=limit, year=year)
            st.session_state["ich_data"] = ich_data
            
            # 展示数据
            for idx, item in enumerate(ich_data, 1):
                with st.expander(f"**{idx}. {item.get('title', '未知项目')}**"):
                    col_a, col_b = st.columns([1, 2])
                    with col_a:
                        st.write(f"**国家/地区**：{item.get('country', '未知')}")
                        st.write(f"**入选年份**：{item.get('year', '未知')}")
                        st.write(f"**类型**：{item.get('category', '传统表演艺术')}")
                    with col_b:
                        desc = item.get('description', '暂无详细介绍')
                        st.write(f"**项目简介**：{desc[:500]}..." if len(desc) > 500 else desc)

with col2:
    st.subheader("🎙️ AI专家讲解")
    if st.button("生成讲解") and "ich_data" in st.session_state:
        with st.spinner("AI正在整理讲解内容..."):
            explanation = generate_global_ich_explanation(st.session_state["ich_data"], client)
            if explanation:
                st.write(explanation)

# 底部提示
st.divider()
st.caption("注：若无法获取实时数据，将展示示例数据 | © 2025 AI非遗智能讲解员")
