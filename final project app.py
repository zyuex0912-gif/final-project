import streamlit as st
import requests
import json
from openai import OpenAI  # 需安装 openai 库（若用其他AI模型可替换）
import time

# ---------------------- 配置项 ----------------------
# API 配置
GBIF_API_URL = "https://api.gbif.org/v1/species"
INATURALIST_API_URL = "https://api.inaturalist.org/v1/taxa"

# OpenAI 配置（可替换为 Claude、Gemini 等其他 AI 模型）
st.secrets["OPENAI_API_KEY"] = st.text_input("请输入你的 OpenAI API Key", type="password")
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

# 动物园馆长角色提示词（核心）
CURATOR_PROMPT = """
你现在是全球顶级动物园的资深馆长，拥有30年动物保育和科普经验，擅长用生动、通俗且专业的语言向参观者介绍动物。
请基于以下动物数据，生成一份完整的解说：
1. 开头用亲切的问候吸引注意力（如“各位参观者，欢迎来到XX展区！”）；
2. 核心内容包含：动物的中文名/英文名/学名、外形特征、生活习性（食性、栖息地、行为特点）、地理分布、保护状态；
3. 加入1-2个趣味冷知识（如独特的生存技能、民间俗称由来等）；
4. 结尾加上保护倡议，传递生态保护理念；
5. 语气友好、口语化，避免过于学术化，适合全年龄段参观者。

动物数据：
{animal_data}
"""

# ---------------------- 工具函数 ----------------------
@st.cache_data(ttl=3600)  # 缓存1小时，避免重复调用API
def fetch_gbif_data(species_name=None, region=None):
    """从 GBIF API 获取物种基础数据（分类、分布、保护状态）"""
    params = {}
    if species_name:
        params["name"] = species_name
        params["rank"] = "SPECIES"  # 只查询物种级数据
    if region:
        params["country"] = region  # 国家代码（如 CN=中国，US=美国）
    
    try:
        response = requests.get(GBIF_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            return data["results"][0]  # 返回第一个匹配结果
        return None
    except Exception as e:
        st.warning(f"GBIF API 调用失败：{str(e)}")
        return None

@st.cache_data(ttl=3600)
def fetch_inaturalist_data(species_name=None, max_photos=3):
    """从 iNaturalist API 获取物种图片、民间观测数据、生活习性"""
    params = {
        "q": species_name,
        "rank": "species",
        "per_page": 1,
        "photos": True
    }
    
    try:
        response = requests.get(INATURALIST_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            result = data["results"][0]
            # 提取关键信息
            inat_data = {
                "common_name": result.get("preferred_common_name"),
                "habitat": result.get("habitat"),
                "behavior": result.get("behavior"),
                "photos": [photo["url"] for photo in result.get("photos", [])[:max_photos]],
                "observations_count": result.get("observations_count", 0)
            }
            return inat_data
        return None
    except Exception as e:
        st.warning(f"iNaturalist API 调用失败：{str(e)}")
        return None

def merge_animal_data(gbif_data, inat_data):
    """合并 GBIF 和 iNaturalist 数据，生成统一的动物信息字典"""
    if not gbif_data:
        return None
    
    merged = {
        "scientific_name": gbif_data.get("scientificName", "未知学名"),
        "chinese_name": gbif_data.get("vernacularName", inat_data.get("common_name", "未知中文名")),
        "english_name": gbif_data.get("englishName", "未知英文名"),
        "classification": {
            "kingdom": gbif_data.get("kingdom"),
            "phylum": gbif_data.get("phylum"),
            "class": gbif_data.get("class"),
            "order": gbif_data.get("order"),
            "family": gbif_data.get("family"),
            "genus": gbif_data.get("genus")
        },
        "distribution": gbif_data.get("distribution", {}).get("countries", ["未知分布"]),
        "conservation_status": gbif_data.get("status", "未知保护状态"),
        "habitat": inat_data.get("habitat", "未知栖息地"),
        "behavior": inat_data.get("behavior", "未知行为习性"),
        "photos": inat_data.get("photos", []),
        "observations_count": inat_data.get("observations_count", 0)
    }
    return merged

def generate_curator_explanation(animal_data):
    """调用 AI 生成动物园馆长风格的解说"""
    if not st.secrets.get("OPENAI_API_KEY"):
        st.error("请先输入你的 OpenAI API Key！")
        return None
    
    prompt = CURATOR_PROMPT.format(animal_data=json.dumps(animal_data, ensure_ascii=False))
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,  # 控制语言生动度
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.warning(f"AI 解说生成失败：{str(e)}")
        return None

# ---------------------- Streamlit 界面设计 ----------------------
st.set_page_config(page_title="AI 动物园馆长", page_icon="🐘", layout="wide")
st.title("🐅 AI 动物园馆长")
st.subheader("—— 基于真实生物数据的智能动物解说")

# 侧边栏：筛选条件
with st.sidebar:
    st.header("🔍 筛选条件")
    region = st.selectbox(
        "选择地区",
        options=["", "CN", "US", "JP", "AU", "DE"],
        format_func=lambda x: {"": "全球", "CN": "中国", "US": "美国", "JP": "日本", "AU": "澳大利亚", "DE": "德国"}[x]
    )
    search_name = st.text_input("输入动物名称（中文/英文）")
    search_btn = st.button("搜索动物")

# 主界面：展示区域
col1, col2 = st.columns([1, 2])  # 左侧图片区，右侧解说区

if search_btn and search_name:
    with st.spinner("正在获取动物数据并生成解说..."):
        # 1. 调用双 API 获取数据
        gbif_data = fetch_gbif_data(species_name=search_name, region=region)
        inat_data = fetch_inaturalist_data(species_name=search_name)
        
        # 2. 合并数据
        animal_data = merge_animal_data(gbif_data, inat_data)
        if not animal_data:
            st.error("未查询到该动物数据，请更换名称或地区重试！")
            st.stop()
        
        # 3. 生成 AI 解说
        explanation = generate_curator_explanation(animal_data)
        
        # 4. 展示结果
        with col1:
            st.subheader(f"🐾 {animal_data['chinese_name']}")
            st.caption(f"学名：{animal_data['scientific_name']}")
            st.caption(f"保护状态：{animal_data['conservation_status']}")
            
            # 展示动物图片
            if animal_data["photos"]:
                for photo in animal_data["photos"]:
                    st.image(photo, use_column_width=True, caption="实拍图片（来自 iNaturalist）")
            else:
                st.image("https://via.placeholder.com/400x300?text=暂无图片", use_column_width=True)
            
            # 基础信息卡片
            st.divider()
            st.info(f"🌍 分布地区：{', '.join(animal_data['distribution'])}")
            st.info(f"🏕️ 栖息地：{animal_data['habitat']}")
            st.info(f"👀 全球观测记录：{animal_data['observations_count']:,} 条")
        
        with col2:
            st.subheader("🎤 馆长解说")
            if explanation:
                st.markdown(f"<div style='font-size:18px; line-height:1.8;'>{explanation}</div>", unsafe_allow_html=True)
            else:
                st.warning("解说生成失败，请检查 API Key 或网络连接！")

else:
    # 初始页面展示示例动物
    st.divider()
    st.subheader("🌟 热门动物推荐")
    
    # 预加载几个常见动物示例
    example_species = ["大熊猫", "非洲象", "东北虎", "蓝鲸"]
    cols = st.columns(len(example_species))
    
    for i, species in enumerate(example_species):
        with cols[i]:
            st.image(f"https://via.placeholder.com/200x150?text={species}", use_column_width=True)
            st.button(f"查看 {species} 解说", key=species, on_click=lambda s=species: st.session_state.update({"selected_example": s}))
    
    # 处理示例动物点击
    if "selected_example" in st.session_state:
        selected_species = st.session_state["selected_example"]
        with st.spinner(f"正在加载 {selected_species} 数据..."):
            gbif_data = fetch_gbif_data(species_name=selected_species)
            inat_data = fetch_inaturalist_data(species_name=selected_species)
            animal_data = merge_animal_data(gbif_data, inat_data)
            explanation = generate_curator_explanation(animal_data)
            
            # 展示示例结果
            with col1:
                st.subheader(f"🐾 {animal_data['chinese_name']}")
                st.caption(f"学名：{animal_data['scientific_name']}")
                if animal_data["photos"]:
                    st.image(animal_data["photos"][0], use_column_width=True, caption="实拍图片（来自 iNaturalist）")
                else:
                    st.image("https://via.placeholder.com/400x300?text=暂无图片", use_column_width=True)
                
                st.divider()
                st.info(f"🌍 分布地区：{', '.join(animal_data['distribution'])}")
                st.info(f"🏕️ 栖息地：{animal_data['habitat']}")
            
            with col2:
                st.subheader("🎤 馆长解说")
                st.markdown(f"<div style='font-size:18px; line-height:1.8;'>{explanation}</div>", unsafe_allow_html=True)

# ---------------------- 底部信息 ----------------------
st.divider()
st.caption("📊 数据来源：GBIF API（全球生物多样性信息网络）、iNaturalist API（公民科学项目）")
st.caption("🤖 AI 模型：OpenAI GPT-3.5 Turbo（可替换为其他大语言模型）")

