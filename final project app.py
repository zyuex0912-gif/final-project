import streamlit as st
import requests
import json
from typing import Optional, Dict, List
from openai import OpenAI
from openai import APIError, AuthenticationError, RateLimitError

# ---------------------- 全局配置（可根据需求修改）----------------------
# API 基础地址
GBIF_API_BASE = "https://api.gbif.org/v1/species"
INATURALIST_API_BASE = "https://api.inaturalist.org/v1/taxa"

# 缓存配置（避免重复调用 API，减轻服务器压力）
CACHE_TTL = 3600  # 缓存有效时间：1小时（秒）
MAX_PHOTOS = 3    # 最大获取图片数量

# 动物园馆长 AI 提示词（核心角色定义）
CURATOR_PROMPT_TEMPLATE = """
你是拥有30年经验的全球顶级动物园馆长，擅长用生动通俗的语言向各年龄段参观者科普动物知识。
请基于以下动物数据，生成结构完整、有趣易懂的解说，要求：
1. 开头亲切问候，点明动物展区主题；
2. 核心内容：中文名/英文名/学名 + 外形特征 + 生活习性（食性/栖息地/行为）+ 地理分布 + 保护状态；
3. 加入1-2个趣味冷知识（如独特生存技能、民间俗称由来等）；
4. 结尾附上保护倡议，传递生态保护理念；
5. 语气友好口语化，避免学术化术语，段落清晰易读。

动物数据：
{animal_data}
"""

# ---------------------- 工具函数 ----------------------
@st.cache_data(ttl=CACHE_TTL, show_spinner="正在获取权威生物数据...")
def fetch_gbif_data(species_name: str, region: str = "") -> Optional[Dict]:
    """
    从 GBIF API 获取物种基础数据（分类、分布、保护状态）
    :param species_name: 物种名称（中文/英文/学名）
    :param region: 国家代码（如 CN=中国，US=美国，空为全球）
    :return: 结构化物种数据字典，失败返回 None
    """
    params = {
        "name": species_name.strip(),
        "rank": "SPECIES",  # 仅查询物种级数据（排除亚种/属等）
        "limit": 1,
        "offset": 0
    }
    if region:
        params["country"] = region

    try:
        response = requests.get(
            GBIF_API_BASE,
            params=params,
            timeout=15,
            headers={"User-Agent": "AI-Zoo-Curator-App/1.0"}
        )
        response.raise_for_status()  # 触发 HTTP 错误（4xx/5xx）
        data = response.json()
        return data["results"][0] if data.get("results") else None
    except requests.exceptions.Timeout:
        st.warning("⚠️ GBIF API 请求超时，请稍后重试")
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ GBIF 数据获取失败：{str(e)}")
    return None

@st.cache_data(ttl=CACHE_TTL, show_spinner="正在获取实拍图片和观测数据...")
def fetch_inaturalist_data(species_name: str) -> Optional[Dict]:
    """
    从 iNaturalist API 获取物种图片、生活习性、民间观测数据
    :param species_name: 物种名称（中文/英文/学名）
    :return: 结构化补充数据字典，失败返回 None
    """
    params = {
        "q": species_name.strip(),
        "rank": "species",
        "per_page": 1,
        "photos": True,
        "lang": "zh"
    }

    try:
        response = requests.get(
            INATURALIST_API_BASE,
            params=params,
            timeout=15,
            headers={"User-Agent": "AI-Zoo-Curator-App/1.0"}
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            return None
        
        result = data["results"][0]
        return {
            "common_name": result.get("preferred_common_name"),
            "habitat": result.get("habitat", "暂无详细记录"),
            "behavior": result.get("behavior", "暂无详细记录"),
            "photos": [photo["url"] for photo in result.get("photos", [])[:MAX_PHOTOS]],
            "observations_count": result.get("observations_count", 0)
        }
    except requests.exceptions.Timeout:
        st.warning("⚠️ iNaturalist API 请求超时，请稍后重试")
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ iNaturalist 数据获取失败：{str(e)}")
    return None

def merge_animal_data(gbif_data: Dict, inat_data: Dict) -> Optional[Dict]:
    """
    合并 GBIF 和 iNaturalist 数据，生成统一结构化数据
    :param gbif_data: GBIF 接口返回数据
    :param inat_data: iNaturalist 接口返回数据
    :return: 合并后的完整动物数据
    """
    if not gbif_data:
        return None

    # 处理分布地区数据
    distribution = gbif_data.get("distribution", {})
    countries = distribution.get("countries", [])
    if not countries:
        countries = ["全球分布" if not distribution else "暂无明确分布记录"]

    return {
        "chinese_name": (
            gbif_data.get("vernacularName") or
            inat_data.get("common_name") or
            "未知中文名"
        ),
        "english_name": gbif_data.get("englishName", "未知英文名"),
        "scientific_name": gbif_data.get("scientificName", "未知学名"),
        "classification": {
            "界": gbif_data.get("kingdom", "未知"),
            "门": gbif_data.get("phylum", "未知"),
            "纲": gbif_data.get("class", "未知"),
            "目": gbif_data.get("order", "未知"),
            "科": gbif_data.get("family", "未知"),
            "属": gbif_data.get("genus", "未知")
        },
        "distribution": countries,
        "conservation_status": gbif_data.get("status", "未知保护状态"),
        "habitat": inat_data.get("habitat", "暂无详细记录"),
        "behavior": inat_data.get("behavior", "暂无详细记录"),
        "photos": inat_data.get("photos", []),
        "observations_count": inat_data.get("observations_count", 0)
    }

def init_ai_client(api_key: str) -> Optional[OpenAI]:
    """初始化 OpenAI 客户端"""
    try:
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"❌ AI 客户端初始化失败：{str(e)}")
        return None

def generate_curator_explanation(animal_data: Dict, api_key: str) -> Optional[str]:
    """
    调用 AI 生成动物园馆长风格解说
    :param animal_data: 合并后的动物数据
    :param api_key: OpenAI API Key
    :return: 生成的解说文本，失败返回 None
    """
    client = init_ai_client(api_key)
    if not client:
        return None

    prompt = CURATOR_PROMPT_TEMPLATE.format(
        animal_data=json.dumps(animal_data, ensure_ascii=False, indent=2)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,  # 控制语言生动度（0=严谨，1=活泼）
            max_tokens=1200,
            timeout=20
        )
        return response.choices[0].message.content.strip()
    except AuthenticationError:
        st.error("❌ API Key 无效或未授权，请检查密钥是否正确")
    except RateLimitError:
        st.error("❌ API 调用频率超限，请稍后重试或升级套餐")
    except APIError as e:
        st.error(f"❌ AI 生成失败：{str(e)}")
    except Exception as e:
        st.error(f"❌ 未知错误：{str(e)}")
    return None

# ---------------------- Streamlit 界面设计 ----------------------
def main():
    # 页面基础配置
    st.set_page_config(
        page_title="AI 动物园馆长",
        page_icon="🐘",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 页面标题与简介
    st.title("🐅 AI 动物园馆长")
    st.subheader("—— 基于全球真实生物数据的智能科普解说", divider="🐾")
    st.markdown("""
    🔍 整合 GBIF 全球生物多样性数据与 iNaturalist 公民科学观测记录  
    🤖 资深馆长风格解说，带趣味冷知识与保护倡议  
    📸 海量实拍图片，支持按地区/名称搜索
    """)

    # 侧边栏配置
    with st.sidebar:
        st.header("🔧 搜索配置", divider="blue")
        
        # API Key 输入（隐藏式）
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-xxx...",
            help="获取地址：https://platform.openai.com/api-keys"
        )
        
        st.header("🔍 筛选条件", divider="blue")
        # 地区选择（国家代码映射）
        region_map = {
            "": "全球",
            "CN": "中国",
            "US": "美国",
            "JP": "日本",
            "AU": "澳大利亚",
            "DE": "德国",
            "FR": "法国",
            "BR": "巴西",
            "ZA": "南非"
        }
        region = st.selectbox("选择地区", options=list(region_map.keys()), format_func=lambda x: region_map[x])
        
        # 动物名称搜索
        search_name = st.text_input("输入动物名称", placeholder="例如：大熊猫、African Elephant、Panthera tigris")
        search_btn = st.button("🔍 搜索动物", type="primary", use_container_width=True)

    # 主内容区布局（左侧图片信息，右侧解说）
    col1, col2 = st.columns([1, 2], gap="large")

    # 热门动物推荐（初始页面）
    if not search_btn and not search_name:
        st.divider()
        st.subheader("🌟 热门动物推荐")
        
        example_species = ["大熊猫", "非洲象", "东北虎", "蓝鲸", "长颈鹿", "北极熊"]
        example_cols = st.columns(len(example_species))
        
        for idx, species in enumerate(example_species):
            with example_cols[idx]:
                st.image(
                    f"https://via.placeholder.com/200x150?text={species}",
                    use_column_width=True,
                    caption=species
                )
                if st.button(f"查看解说", key=f"example_{species}", use_container_width=True):
                    st.session_state["selected_example"] = species

    # 处理搜索/示例点击
    if search_btn and search_name:
        process_animal_query(search_name, region, api_key, col1, col2)
    elif "selected_example" in st.session_state:
        selected_species = st.session_state["selected_example"]
        process_animal_query(selected_species, "", api_key, col1, col2)

    # 底部信息
    st.divider()
    st.caption("""
    📊 数据来源：GBIF API | iNaturalist API  
    🤖 AI 模型：OpenAI GPT-3.5 Turbo（支持替换为 Claude/Gemini 等）  
    ⚠️ 本应用仅用于科普，数据以官方发布为准
    """)

def process_animal_query(species_name: str, region: str, api_key: str, col1, col2):
    """处理动物查询请求并展示结果"""
    with st.spinner(f"正在为你查找 {species_name} 的资料..."):
        # 1. 获取双 API 数据
        gbif_data = fetch_gbif_data(species_name, region)
        inat_data = fetch_inaturalist_data(species_name)
        
        # 2. 合并数据
        animal_data = merge_animal_data(gbif_data, inat_data)
        if not animal_data:
            st.error(f"❌ 未查询到 {species_name} 的相关数据，请尝试：")
            st.markdown("1. 更换更精准的名称（如学名）")
            st.markdown("2. 移除地区限制")
            st.markdown("3. 检查拼写是否正确")
            return

        # 3. 生成 AI 解说
        explanation = generate_curator_explanation(animal_data, api_key) if api_key else None

        # 4. 左侧展示：图片 + 基础信息
        with col1:
            st.subheader(f"🐾 {animal_data['chinese_name']}", divider="red")
            st.caption(f"学名：{animal_data['scientific_name']}")
            st.caption(f"英文名：{animal_data['english_name']}")

            # 展示图片
            if animal_data["photos"]:
                for idx, photo in enumerate(animal_data["photos"]):
                    st.image(
                        photo,
                        use_column_width=True,
                        caption=f"实拍图片 {idx+1}（来自 iNaturalist）"
                    )
            else:
                st.image(
                    "https://via.placeholder.com/400x300?text=暂无实拍图片",
                    use_column_width=True,
                    caption="暂无实拍图片"
                )

            # 基础信息卡片
            st.divider()
            st.info(f"🌍 分布地区：{', '.join(animal_data['distribution'])}")
            st.info(f"🏕️ 栖息地：{animal_data['habitat']}")
            st.info(f"🛡️ 保护状态：{animal_data['conservation_status']}")
            st.info(f"👀 全球观测：{animal_data['observations_count']:,} 条记录")

            # 分类信息
            st.divider()
            st.subheader("📚 分类归属")
            for rank, value in animal_data["classification"].items():
                st.markdown(f"**{rank}**：{value}")

        # 5. 右侧展示：AI 馆长解说
        with col2:
            st.subheader("🎤 馆长现场解说", divider="blue")
            if explanation:
                st.markdown(f"<div style='font-size: 17px; line-height: 1.8;'>{explanation}</div>", unsafe_allow_html=True)
            else:
                st.warning("""
                ⚠️ 解说未生成，请先在侧边栏输入有效的 OpenAI API Key  
                👉 若没有 API Key，可替换代码中的 AI 模型为免费替代方案（如 Claude、Gemini）
                """)

if __name__ == "__main__":
    main()

