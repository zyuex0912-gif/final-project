import streamlit as st
import requests
import json
from typing import Optional, Dict, List
from openai import OpenAI
from openai import APIError, AuthenticationError, RateLimitError

# ---------------------- Global Configuration (Editable) ----------------------
# API Base URLs
GBIF_API_BASE = "https://api.gbif.org/v1/species"
INATURALIST_API_BASE = "https://api.inaturalist.org/v1/taxa"

# Cache Configuration (Reduce API calls)
CACHE_TTL = 3600  # Cache validity: 1 hour (seconds)
MAX_PHOTOS = 3    # Maximum number of photos to fetch

# 多角色风格提示词模板
DIRECTOR_PROMPT_TEMPLATES = {
    "general": """
You are a senior director with 30 years of experience in a world-class zoo, 
skilled at explaining animal knowledge to general visitors in vivid, accessible language.
Based on the following animal data, generate a complete, engaging explanation that includes:
1. A warm opening greeting to attract attention (e.g., "Welcome to the XX exhibit, everyone!");
2. Core content: Common name / English name / Scientific name + Physical characteristics + 
   Lifestyle (diet, habitat, behavior) + Geographic distribution + Conservation status;
3. 1-2 fun trivia facts (e.g., unique survival skills, origin of common nicknames);
4. A conservation initiative at the end to promote ecological protection awareness;
5. Friendly and colloquial tone, avoid excessive academic jargon, clear paragraphs for easy reading.

Animal Data:
{animal_data}
""",
    "kids": """
You are a zoo director specialized in educating children (ages 6-12), with a playful, energetic tone.
Based on the following animal data, generate a kid-friendly explanation that includes:
1. A cheerful, exciting opening (e.g., "Hey little explorers! Let's meet the amazing XX!");
2. Core content: Simple descriptions of appearance (cute/fun features), diet (favorite foods), 
   interesting behaviors (funny habits, unique skills) + basic habitat information;
3. 2-3 fun, surprising trivia facts (e.g., "Did you know? This animal can...!");
4. A simple, actionable conservation message (e.g., "Let's help protect their homes by...");
5. Use short sentences, exclamation points appropriately, avoid complex words, add emoji-like language.

Animal Data:
{animal_data}
""",
    "biologist": """
You are a senior zoo director with a background in wildlife biology, speaking to professional biologists/students.
Based on the following animal data, generate a technical, detailed explanation that includes:
1. A concise opening introducing the species' ecological significance;
2. Core content: Complete taxonomic classification + detailed morphological characteristics + 
   ecological niche (dietary strategy, habitat specificity, interspecies interactions) + 
   population dynamics + conservation status (with IUCN category if available) + genetic relatedness;
3. Latest research findings or taxonomic updates (if relevant);
4. Conservation challenges and scientific management strategies;
5. Academic but accessible tone, use standard biological terminology, provide precise data where possible.

Animal Data:
{animal_data}
""",
    "tourist_guide": """
You are an experienced zoo tour guide, speaking to casual tourists seeking an engaging, memorable experience.
Based on the following animal data, generate a lively, story-driven explanation that includes:
1. An inviting opening that builds curiosity (e.g., "Keep your eyes peeled—you're about to meet one of our most fascinating residents!");
2. Core content: Highlight the most striking/unique features + interesting behavioral anecdotes + 
   cultural significance or folklore (if relevant) + best viewing tips (what to look for);
3. 1-2 surprising "did you know" facts to impress visitors;
4. A heartfelt conservation message that connects to visitors' experience;
5. Conversational tone, use storytelling elements, keep it engaging but not too technical.

Animal Data:
{animal_data}
"""
}

# 角色风格说明（用于UI展示）
ROLE_DESCRIPTIONS = {
    "general": "General Visitors (Friendly & Balanced) - Suitable for all ages, mix of fun and information",
    "kids": "Children (Playful & Simple) - Age 6-12, fun facts and easy-to-understand language",
    "biologist": "Biologists/Students (Technical & Detailed) - Professional terminology and in-depth data",
    "tourist_guide": "Casual Tourists (Engaging & Story-driven) - Memorable stories and viewing tips"
}

# 大熊猫默认数据（无需API调用，初始界面直接展示）
GIANT_PANDA_DEFAULT_DATA = {
    "common_name": "Giant Panda",
    "chinese_name": "大熊猫",
    "english_name": "Giant Panda",
    "scientific_name": "Ailuropoda melanoleuca",
    "classification": {
        "Kingdom": "Animalia",
        "Phylum": "Chordata",
        "Class": "Mammalia",
        "Order": "Carnivora",
        "Family": "Ursidae",
        "Genus": "Ailuropoda"
    },
    "distribution": ["China"],
    "conservation_status": "Vulnerable (VU)",
    "habitat": "Temperate broadleaf and mixed forests with dense bamboo stands, primarily in Sichuan, Shaanxi, and Gansu provinces of China",
    "behavior": "Primarily herbivorous (99% bamboo diet), solitary except during breeding season, excellent climbers, spend 10-16 hours daily feeding",
    "photos": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/1200px-Grosser_Panda.JPG",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Panda_%2828908900398%29.jpg/1200px-Panda_%2828908900398%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Giant_Panda_%28Ailuropoda_melanoleuca%29.jpg/1200px-Giant_Panda_%28Ailuropoda_melanoleuca%29.jpg"
    ],
    "observations_count": 158000,
    "default_explanation": {
        "general": """
Welcome to the Giant Panda exhibit, everyone! It's a pleasure to introduce you to one of the world's most beloved and iconic animals—the Giant Panda (Ailuropoda melanoleuca)!

These fluffy black-and-white mammals are instantly recognizable with their round faces, black patches around their eyes, and stocky bodies. Despite being classified as carnivores, pandas have evolved to be almost exclusively herbivorous, with bamboo making up 99% of their diet. They can eat up to 12-38 kilograms of bamboo per day, spending 10-16 hours feeding to meet their energy needs!

In the wild, giant pandas are found only in the mountainous regions of central China, primarily in Sichuan, Shaanxi, and Gansu provinces. They inhabit temperate broadleaf and mixed forests with dense bamboo stands, which provide both food and shelter. Once endangered, their conservation status has improved to "Vulnerable" thanks to extensive protection efforts, including habitat preservation and captive breeding programs.

Fun trivia: Did you know that pandas have a specialized sixth finger (a modified wrist bone) that acts like an opposable thumb? This unique adaptation helps them grasp bamboo stalks with precision! Another interesting fact—pandas have a very low metabolic rate, similar to sloths, which is why they move slowly and sleep for much of the day.

As we admire these amazing creatures, let's remember the importance of protecting their natural habitats. Deforestation and habitat fragmentation remain threats to their survival. By supporting conservation initiatives and sustainable practices, we can ensure that giant pandas continue to thrive for generations to come. Enjoy your time watching these gentle giants!
        """,
        "kids": """
Hey little explorers! Let's meet the amazing Giant Panda—one of the cutest and most famous animals on Earth! 🐼

Look at their fluffy black-and-white fur! They have big round faces, black "eye masks" that make them look like little superheroes, and chubby bodies that waddle when they walk—so adorable! Pandas love bamboo more than anything else—they eat it for breakfast, lunch, and dinner! They munch on 12-38 kilograms of bamboo every day—that's like eating 100 bowls of rice! Yum!

Pandas live in the mountains of China, in forests where there are lots of bamboo plants. They're great climbers and can even climb trees when they want to take a nap or escape from trouble. Unlike other bears, pandas don't hibernate—they just move to warmer areas in the winter.

Did you know? 🤯 Pandas have a secret "extra finger"! It's not a real finger, but a special bone in their wrist that helps them hold bamboo like we hold a pencil. And baby pandas are called cubs—they're only about the size of a stick of butter when they're born, and they're pink and hairless! How cool is that?

Let's help protect pandas! We can do simple things like saving paper (since paper comes from trees) and supporting zoos that help breed pandas. Every little bit helps these cute creatures keep their homes safe. Now, let's watch them munch bamboo—they're so good at it!
        """,
        "biologist": """
The Giant Panda (Ailuropoda melanoleuca) holds significant ecological and taxonomic importance as a member of the Ursidae family, representing a unique lineage within the Carnivora order. This species exhibits distinct morphological, behavioral, and physiological adaptations that make it a focal point of evolutionary biology research.

Taxonomically, Ailuropoda melanoleuca is classified under Kingdom Animalia, Phylum Chordata, Class Mammalia, Order Carnivora, Family Ursidae, and Genus Ailuropoda. Phylogenetic studies indicate that pandas diverged from other bear species approximately 19-24 million years ago, with genetic analyses supporting their placement within the bear family rather than a separate family (Ailuropodidae).

Morphologically, pandas display several specialized adaptations for their bamboo-dominated diet: a modified radial sesamoid bone (the "sixth finger") for grasping bamboo, robust jaw muscles and molar teeth for chewing tough plant material, and a reduced digestive tract (relative to other herbivores) despite their herbivorous diet. Their digestive system retains carnivorous characteristics, with low efficiency in cellulose digestion—compensated by high intake volumes (12-38 kg/day of bamboo).

Ecologically, pandas occupy a narrow niche in temperate broadleaf and mixed forests at elevations of 1,200-3,400 meters in central China. Their distribution is limited to fragmented habitats in Sichuan, Shaanxi, and Gansu provinces, with an estimated wild population of 1,864 individuals (2021 census). The species is classified as Vulnerable (VU) by the IUCN Red List, with primary threats including habitat fragmentation, climate change-induced bamboo die-offs, and human-wildlife conflict.

Population management strategies include habitat connectivity projects (e.g., the Giant Panda National Park, established in 2020), captive breeding programs with a success rate of ~80% in major facilities, and genetic monitoring to maintain genetic diversity. Recent research has focused on the species' gut microbiome adaptation to bamboo digestion and the impact of climate change on bamboo phenology.

Conservation challenges persist, particularly regarding habitat fragmentation and the long-term sustainability of bamboo forests. Continued scientific research, habitat protection, and community engagement are critical for the species' long-term survival.
        """,
        "tourist_guide": """
Keep your eyes peeled—you're about to meet one of our most fascinating residents: the Giant Panda! These gentle giants are not just cute—they're living symbols of conservation success and cultural heritage.

As you watch them munch bamboo, notice their iconic black-and-white markings—each panda's pattern is unique, like a fingerprint! Those black patches around their eyes aren't just for show—scientists think they help reduce glare from the sun and may also serve as a form of communication. And that waddling walk? It's due to their short legs and stocky build, which are perfect for climbing trees but make walking on the ground a little comical.

Pandas have deep cultural significance in China, where they're considered a national treasure and a symbol of peace. For centuries, they've been featured in art, literature, and folklore. But beyond their cultural importance, they're also ecological indicators—their presence means the forest ecosystem is healthy.

Pro tip: Look closely at how they hold the bamboo—they use their "sixth finger" to grip stalks with amazing precision. If you're lucky, you might see them do a little somersault or climb a tree—they're surprisingly agile for their size! And don't worry if they seem lazy—pandas sleep up to 14 hours a day to conserve energy from their low-nutrient bamboo diet.

Did you know that pandas were once endangered? Thanks to decades of conservation efforts, their population has grown, and they're now classified as Vulnerable. But their habitat is still under threat, so every time we support conservation, we're helping these amazing animals thrive.

Take a moment to appreciate these gentle giants—they're a reminder of how human action can make a positive difference. Enjoy the view, and feel free to ask if you have any questions!
        """
    }
}

# ---------------------- Utility Functions ----------------------
@st.cache_data(ttl=CACHE_TTL, show_spinner="Fetching authoritative biodiversity data...")
def fetch_gbif_data(species_name: str, region: str = "") -> Optional[Dict]:
    """
    Fetch basic species data (classification, distribution, conservation status) from GBIF API
    :param species_name: Animal name (Common name / English name / Scientific name)
    :param region: Country code (e.g., CN=China, US=United States, empty=global)
    :return: Structured species data dict, None if failed
    """
    params = {
        "name": species_name.strip(),
        "rank": "SPECIES",  # Only fetch species-level data (exclude subspecies/genus)
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
            headers={"User-Agent": "AI-Zoo-Director-App/1.0"}
        )
        response.raise_for_status()  # Trigger HTTP errors (4xx/5xx)
        data = response.json()
        return data["results"][0] if data.get("results") else None
    except requests.exceptions.Timeout:
        st.warning("⚠️ GBIF API request timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ Failed to fetch GBIF data: {str(e)}")
    return None

@st.cache_data(ttl=CACHE_TTL, show_spinner="Fetching real photos and observation data...")
def fetch_inaturalist_data(species_name: str) -> Optional[Dict]:
    """
    Fetch species photos, lifestyle, and citizen science data from iNaturalist API
    :param species_name: Animal name (Common name / English name / Scientific name)
    :return: Structured supplementary data dict, None if failed
    """
    params = {
        "q": species_name.strip(),
        "rank": "species",
        "per_page": 1,
        "photos": True,
        "lang": "en"
    }

    try:
        response = requests.get(
            INATURALIST_API_BASE,
            params=params,
            timeout=15,
            headers={"User-Agent": "AI-Zoo-Director-App/1.0"}
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("results"):
            return None
        
        result = data["results"][0]
        return {
            "common_name": result.get("preferred_common_name"),
            "habitat": result.get("habitat", "No detailed records available"),
            "behavior": result.get("behavior", "No detailed records available"),
            "photos": [photo["url"] for photo in result.get("photos", [])[:MAX_PHOTOS]],
            "observations_count": result.get("observations_count", 0)
        }
    except requests.exceptions.Timeout:
        st.warning("⚠️ iNaturalist API request timed out. Please try again later.")
    except requests.exceptions.RequestException as e:
        st.warning(f"⚠️ Failed to fetch iNaturalist data: {str(e)}")
    return None

def merge_animal_data(gbif_data: Dict, inat_data: Dict) -> Optional[Dict]:
    """
    Merge GBIF and iNaturalist data into a unified structured format
    :param gbif_data: Data from GBIF API
    :param inat_data: Data from iNaturalist API
    :return: Merged complete animal data dict
    """
    if not gbif_data:
        return None

    # Process distribution data
    distribution = gbif_data.get("distribution", {})
    countries = distribution.get("countries", [])
    if not countries:
        countries = ["Global distribution" if not distribution else "No clear distribution records"]

    return {
        "common_name": (
            gbif_data.get("vernacularName") or
            inat_data.get("common_name") or
            "Unknown common name"
        ),
        "chinese_name": gbif_data.get("vernacularName") or "Unknown Chinese name",
        "english_name": gbif_data.get("englishName", "Unknown English name"),
        "scientific_name": gbif_data.get("scientificName", "Unknown scientific name"),
        "classification": {
            "Kingdom": gbif_data.get("kingdom", "Unknown"),
            "Phylum": gbif_data.get("phylum", "Unknown"),
            "Class": gbif_data.get("class", "Unknown"),
            "Order": gbif_data.get("order", "Unknown"),
            "Family": gbif_data.get("family", "Unknown"),
            "Genus": gbif_data.get("genus", "Unknown")
        },
        "distribution": countries,
        "conservation_status": gbif_data.get("status", "Unknown conservation status"),
        "habitat": inat_data.get("habitat", "No detailed records available"),
        "behavior": inat_data.get("behavior", "No detailed records available"),
        "photos": inat_data.get("photos", []),
        "observations_count": inat_data.get("observations_count", 0)
    }

def init_ai_client(api_key: str) -> Optional[OpenAI]:
    """Initialize OpenAI client"""
    try:
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Failed to initialize AI client: {str(e)}")
        return None

def generate_director_explanation(animal_data: Dict, api_key: str, selected_role: str) -> Optional[str]:
    """
    Generate zoo director-style explanation via AI with selected role
    :param animal_data: Merged animal data
    :param api_key: OpenAI API Key
    :param selected_role: Selected explanation style (general/kids/biologist/tourist_guide)
    :return: Generated explanation text, None if failed
    """
    # 若为大熊猫且未输入API Key，返回默认解说
    if animal_data.get("scientific_name") == "Ailuropoda melanoleuca" and not api_key:
        return GIANT_PANDA_DEFAULT_DATA["default_explanation"][selected_role].strip()
    
    client = init_ai_client(api_key)
    if not client:
        return None

    # Get corresponding prompt template based on selected role
    prompt = DIRECTOR_PROMPT_TEMPLATES[selected_role].format(
        animal_data=json.dumps(animal_data, ensure_ascii=False, indent=2)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7 if selected_role != "biologist" else 0.3,  # 科学家风格更严谨，降低随机性
            max_tokens=800,
            timeout=20
        )
        return response.choices[0].message.content.strip()
    except AuthenticationError:
        st.error("❌ Invalid or unauthorized API Key. Please check your key.")
    except RateLimitError:
        st.error("❌ API rate limit exceeded. Please try again later or upgrade your plan.")
    except APIError as e:
        st.error(f"❌ AI generation failed: {str(e)}")
    except Exception as e:
        st.error(f"❌ Unknown error: {str(e)}")
    return None

# ---------------------- Streamlit UI Design ----------------------
def main():
    # Page Basic Configuration
    st.set_page_config(
        page_title="AI Zoo Director",
        page_icon="🐘",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Page Title & Introduction
    st.title("🐅 AI Zoo Director")
    st.subheader("—— Intelligent Science Explanations Based on Global Biodiversity Data", divider="orange")
    st.markdown("""
    🔍 Integrates GBIF global biodiversity data & iNaturalist citizen science records  
    🎭 Multiple director styles for different audiences (Kids / Biologists / Tourists)  
    📸 Massive real photos, support search by name & region  
    🐼 Default display: Giant Panda (No API Key required!)
    """)

    # Sidebar Configuration
    with st.sidebar:
        st.header("🔧 Search Settings", divider="blue")
        
        # API Key Input (Hidden)
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-xxx...",
            help="Get API Key: https://platform.openai.com/api-keys (Required for non-panda animals)"
        )
        
        # 角色风格选择
        st.header("🎭 Director Style", divider="blue")
        selected_role = st.selectbox(
            "Select Audience Style",
            options=list(DIRECTOR_PROMPT_TEMPLATES.keys()),
            format_func=lambda x: x.replace("_", " ").title(),
            index=0  # 默认选择 general
        )
        # 显示角色风格说明
        st.caption(f"ℹ️ {ROLE_DESCRIPTIONS[selected_role]}")
        
        st.header("🔍 Filter Options", divider="blue")
        # Region Selection (Country Code Mapping)
        region_map = {
            "": "Global",
            "CN": "China",
            "US": "United States",
            "JP": "Japan",
            "AU": "Australia",
            "DE": "Germany",
            "FR": "France",
            "BR": "Brazil",
            "ZA": "South Africa",
            "UK": "United Kingdom",
            "CA": "Canada"
        }
        region = st.selectbox("Select Region", options=list(region_map.keys()), format_func=lambda x: region_map[x])
        
        # Animal Name Search
        search_name = st.text_input("Enter Animal Name", placeholder="e.g., African Elephant, Siberian Tiger, Panthera tigris")
        search_btn = st.button("🔍 Search Animal", type="primary", use_container_width=True)

    # Main Content Layout (Left: Images & Info, Right: Explanation)
    col1, col2 = st.columns([1, 2], gap="large")

    # 初始页面：默认展示大熊猫（无需搜索）
    if not search_btn and not search_name and "selected_example" not in st.session_state:
        st.divider()
        st.subheader("🐼 Featured Animal: Giant Panda")
        
        # 左侧：大熊猫基础信息
        with col1:
            st.subheader(f"🐾 {GIANT_PANDA_DEFAULT_DATA['common_name']} ({GIANT_PANDA_DEFAULT_DATA['chinese_name']})", divider="red")
            st.caption(f"Scientific Name: {GIANT_PANDA_DEFAULT_DATA['scientific_name']}")
            st.caption(f"English Name: {GIANT_PANDA_DEFAULT_DATA['english_name']}")

            # 展示大熊猫实拍图片
            for idx, photo in enumerate(GIANT_PANDA_DEFAULT_DATA["photos"]):
                st.image(
                    photo,
                    use_column_width=True,
                    caption=f"Real Photo {idx+1} (Giant Panda in China)"
                )

            # 基础信息卡片
            st.divider()
            st.info(f"🌍 Distribution: {', '.join(GIANT_PANDA_DEFAULT_DATA['distribution'])}")
            st.info(f"🏕️ Habitat: {GIANT_PANDA_DEFAULT_DATA['habitat'][:100]}...")  # 截断长文本
            st.info(f"🛡️ Conservation Status: {GIANT_PANDA_DEFAULT_DATA['conservation_status']}")
            st.info(f"👀 Global Observations: {GIANT_PANDA_DEFAULT_DATA['observations_count']:,} records")

            # 分类归属
            st.divider()
            st.subheader("📚 Taxonomy")
            for rank, value in GIANT_PANDA_DEFAULT_DATA["classification"].items():
                st.markdown(f"**{rank}**：{value}")

        # 右侧：大熊猫默认解说（根据选择的角色）
        with col2:
            role_display_name = selected_role.replace("_", " ").title()
            st.subheader(f"🎤 Director's Explanation (For {role_display_name})", divider="blue")
            st.markdown(f"<div style='font-size: 17px; line-height: 1.8;'>{GIANT_PANDA_DEFAULT_DATA['default_explanation'][selected_role]}</div>", unsafe_allow_html=True)
        
        # 热门动物推荐（默认展示大熊猫下方）
        st.divider()
        st.subheader("🌟 More Popular Animals")
        example_species = ["African Elephant", "Siberian Tiger", "Blue Whale", "Giraffe", "Polar Bear"]
        example_cols = st.columns(len(example_species))
        
        for idx, species in enumerate(example_species):
            with example_cols[idx]:
                st.image(
                    f"https://via.placeholder.com/200x150?text={species}",
                    use_column_width=True,
                    caption=species
                )
                if st.button(f"View Explanation", key=f"example_{species}", use_container_width=True):
                    st.session_state["selected_example"] = species

    # 处理搜索/其他动物示例点击
    elif search_btn and search_name:
        process_animal_query(search_name, region, api_key, selected_role, col1, col2)
    elif "selected_example" in st.session_state:
        selected_species = st.session_state["selected_example"]
        process_animal_query(selected_species, "", api_key, selected_role, col1, col2)

    # Footer Information
    st.divider()
    st.caption("""
    📊 Data Sources: GBIF API | iNaturalist API | Giant Panda default data (authoritative conservation records)  
    🤖 AI Model: OpenAI gpt-4o-mini  
    """)

def process_animal_query(species_name: str, region: str, api_key: str, selected_role: str, col1, col2):
    """Process animal search query and display results with selected role style"""
    with st.spinner(f"Searching for {species_name}..."):
        # 特殊处理：如果搜索大熊猫，使用默认数据
        if species_name.lower() in ["giant panda", "大熊猫", "ailuropoda melanoleuca"]:
            animal_data = GIANT_PANDA_DEFAULT_DATA
        else:
            # 1. 获取双 API 数据
            gbif_data = fetch_gbif_data(species_name, region)
            inat_data = fetch_inaturalist_data(species_name)
            
            # 2. 合并数据
            animal_data = merge_animal_data(gbif_data, inat_data)
            if not animal_data:
                st.error(f"❌ No data found for {species_name}. Please try:")
                st.markdown("1. Use a more precise name (e.g., scientific name)")
                st.markdown("2. Remove region filter")
                st.markdown("3. Check spelling")
                return

        # 3. 生成 AI 解说（大熊猫无需API Key）
        if animal_data.get("scientific_name") == "Ailuropoda melanoleuca":
            explanation = animal_data["default_explanation"][selected_role].strip()
        else:
            if not api_key:
                st.error("❌ API Key is required for non-panda animals. Please enter your OpenAI API Key in the sidebar.")
                return
            explanation = generate_director_explanation(animal_data, api_key, selected_role)
            if not explanation:
                return

        # 4. 左侧展示：图片 + 基础信息
        with col1:
            chinese_name = animal_data.get("chinese_name", "")
            if chinese_name and chinese_name != "Unknown Chinese name":
                st.subheader(f"🐾 {animal_data['common_name']} ({chinese_name})", divider="red")
            else:
                st.subheader(f"🐾 {animal_data['common_name']}", divider="red")
            st.caption(f"Scientific Name: {animal_data['scientific_name']}")
            st.caption(f"English Name: {animal_data['english_name']}")

            # 展示图片
            if animal_data["photos"]:
                for idx, photo in enumerate(animal_data["photos"]):
                    st.image(
                        photo,
                        use_column_width=True,
                        caption=f"Real Photo {idx+1} (from iNaturalist)" if "default_explanation" not in animal_data else f"Real Photo {idx+1} (Giant Panda in China)"
                    )
            else:
                st.image(
                    "https://via.placeholder.com/400x300?text=No+Photos+Available",
                    use_column_width=True,
                    caption="No Photos Available"
                )

            # 基础信息卡片
            st.divider()
            st.info(f"🌍 Distribution: {', '.join(animal_data['distribution'])}")
            st.info(f"🏕️ Habitat: {animal_data['habitat'][:100]}..." if len(animal_data['habitat']) > 100 else f"🏕️ Habitat: {animal_data['habitat']}")
            st.info(f"🛡️ Conservation Status: {animal_data['conservation_status']}")
            st.info(f"👀 Global Observations: {animal_data['observations_count']:,} records")

            # 分类信息
            st.divider()
            st.subheader("📚 Taxonomy")
            for rank, value in animal_data["classification"].items():
                st.markdown(f"**{rank}**：{value}")

        # 5. 右侧展示：AI 馆长解说
        with col2:
            role_display_name = selected_role.replace("_", " ").title()
            st.subheader(f"🎤 Director's Explanation (For {role_display_name})", divider="blue")
            
            if explanation:
                st.markdown(f"<div style='font-size: 17px; line-height: 1.8;'>{explanation}</div>", unsafe_allow_html=True)
            else:
                st.warning("""
                ⚠️ Explanation not generated. Please enter a valid OpenAI API Key in the sidebar.  
                👉 If you don't have an API Key, replace the AI model in the code with free alternatives (e.g., Claude, Gemini).
                """)

if __name__ == "__main__":
    main()
