import streamlit as st
import requests
import json

# 1. 定义API调用函数
def get_unesco_ich_data(region="Asia", limit=5, year=None):
    """
    调用UNESCO Explore API获取非物质文化遗产数据
    :param region: 地区（如Asia, Europe, Africa）
    :param limit: 返回数据条数
    :param year: 入选年份（可选，如2010）
    :return: 非遗数据列表
    """
    # 基础API URL
    base_url = "https://data.unesco.org/api/explore/v2.0/catalog/datasets/intangible-heritage/records"
    
    # 构建参数（筛选条件）
    params = {
        "limit": limit,
        "refine": f"region:{region}"  # 地区筛选
    }
    
    # 若指定年份，添加年份筛选
    if year:
        params["refine"] += f",year:{year}"
    
    # 发起请求
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # 若状态码非200，抛出异常
        data = response.json()
        return data["results"]  # 返回结果列表（核心数据在"results"字段）
    except Exception as e:
        st.error(f"获取UNESCO非遗数据失败：{str(e)}")
        return []

# 2. Streamlit界面集成
st.title("🌍 全球非遗数据（UNESCO官方）")
st.subheader("—— AI非遗智能讲解员 · 全球视角")

# 侧边栏：用户筛选条件
with st.sidebar:
    st.header("筛选条件")
    region = st.selectbox("选择地区", ["Asia（亚洲）", "Europe（欧洲）", "Africa（非洲）", "Americas（美洲）"], index=0)
    # 提取地区英文（适配API参数）
    region_en = region.split("（")[0]
    year = st.number_input("入选年份（可选，如2010）", min_value=2003, max_value=2024, value=None, step=1)
    limit = st.slider("返回数据条数", min_value=1, max_value=20, value=5)

# 主内容区：展示非遗数据
if st.button("获取全球非遗数据"):
    with st.spinner("正在从UNESCO获取数据..."):
        ich_data = get_unesco_ich_data(region=region_en, limit=limit, year=year)
        if ich_data:
            for idx, item in enumerate(ich_data, 1):
                # 提取核心信息（字段名参考API返回结果，可能因数据集更新略有变化）
                title = item.get("title", "未知项目名称")  # 项目名称（多语言，默认英文）
                country = item.get("country", "未知国家/地区")  # 申报国家/地区
                year_selected = item.get("year", "未知年份")  # 入选年份
                description = item.get("description", "暂无描述")  # 项目描述（部分为英文）
                
                # 分栏展示：左侧标题，右侧详情
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(f"**{idx}. {title}**")
                    st.caption(f"国家：{country}")
                    st.caption(f"入选：{year_selected}年")
                with col2:
                    st.write("**项目简介**：", description[:300] + "..." if len(description) > 300 else description)
                st.divider()  # 分隔线
from openai import OpenAI
import os

# 初始化OpenAI客户端（需配置环境变量OPENAI_API_KEY）
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_global_ich_explanation(ich_data):
    """基于UNESCO非遗数据生成AI讲解"""
    # 整理数据为自然语言描述
    data_summary = ""
    for item in ich_data:
        data_summary += f"- 项目：{item.get('title')}，国家：{item.get('country')}，入选年份：{item.get('year')}，简介：{item.get('description')[:100]}...\n"
    
    # 提示词设计（融合“全球非遗专家”角色）
    prompt = f"""你是全球非物质文化遗产专家，基于以下UNESCO官方数据，生成一段生动的讲解：
    数据：{data_summary}
    要求：1. 介绍这些非遗项目的共性（如文化价值、保护挑战）；2. 对比不同地区项目的特色；3. 语言通俗，适合大众理解；4. 结尾提出一个互动问题（如“你还知道哪些亚洲非遗项目？”）。"""
    
    # 调用大模型生成讲解
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8
    )
    return response.choices[0].message.content

# Streamlit界面中添加“生成讲解”按钮
if ich_data:
    if st.button("生成全球非遗讲解"):
        with st.spinner("AI专家正在准备讲解..."):
            explanation = generate_global_ich_explanation(ich_data)
            st.subheader("🌐 AI全球非遗专家讲解")
            st.write(explanation)
