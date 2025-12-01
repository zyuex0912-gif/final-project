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

# AI Zoo Curator Prompt (Core Role Definition)
CURATOR_PROMPT_TEMPLATE = """
You are a senior curator with 30 years of experience in a world-class zoo, 
skilled at explaining animal knowledge to visitors of all ages in vivid, accessible language.
Based on the following animal data, generate a complete, engaging explanation that includes:
1. A warm opening greeting to attract attention (e.g., "Welcome to the XX exhibit, everyone!");
2. Core content: Common name / English name / Scientific name + Physical characteristics + 
   Lifestyle (diet, habitat, behavior) + Geographic distribution + Conservation status;
3. 1-2 fun trivia facts (e.g., unique survival skills, origin of common nicknames);
4. A conservation initiative at the end to promote ecological protection awareness;
5. Friendly and colloquial tone, avoid academic jargon, with clear paragraphs for easy reading.

Animal Data:
{animal_data}
"""

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
            headers={"User-Agent": "AI-Zoo-Curator-App/1.0"}
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
            headers={"User-Agent": "AI-Zoo-Curator-App/1.0"}
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

def generate_curator_explanation(animal_data: Dict, api_key: str) -> Optional[str]:
    """
    Generate zoo curator-style explanation via AI
    :param animal_data: Merged animal data
    :param api_key: OpenAI API Key
    :return: Generated explanation text, None if failed
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
            temperature=0.7,  # Control language vividness (0=rigid, 1=creative)
            max_tokens=1200,
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
        page_title="AI Zoo Curator",
        page_icon="🐘",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Page Title & Introduction
    st.title("🐅 AI Zoo Curator")
    st.subheader("—— Intelligent Science Explanations Based on Global Biodiversity Data", divider="orange")
    st.markdown("""
    🔍 Integrates GBIF global biodiversity data & iNaturalist citizen science records  
    🤖 Senior curator-style explanations with fun trivia & conservation messages  
    📸 Massive real photos, support search by name & region
    """)

    # Sidebar Configuration
    with st.sidebar:
        st.header("🔧 Search Settings", divider="blue")
        
        # API Key Input (Hidden)
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-xxx...",
            help="Get API Key: https://platform.openai.com/api-keys"
        )
        
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
        search_name = st.text_input("Enter Animal Name", placeholder="e.g., Giant Panda, African Elephant, Panthera tigris")
        search_btn = st.button("🔍 Search Animal", type="primary", use_container_width=True)

    # Main Content Layout (Left: Images & Info, Right: Explanation)
    col1, col2 = st.columns([1, 2], gap="large")

    # Popular Animals Recommendation (Initial Page)
    if not search_btn and not search_name:
        st.divider()
        st.subheader("🌟 Popular Animal Recommendations")
        
        example_species = ["Giant Panda", "African Elephant", "Siberian Tiger", "Blue Whale", "Giraffe", "Polar Bear"]
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

    # Process Search/Example Click
    if search_btn and search_name:
        process_animal_query(search_name, region, api_key, col1, col2)
    elif "selected_example" in st.session_state:
        selected_species = st.session_state["selected_example"]
        process_animal_query(selected_species, "", api_key, col1, col2)

    # Footer Information
    st.divider()
    st.caption("""
    📊 Data Sources: GBIF API | iNaturalist API  
    🤖 AI Model: OpenAI GPT-3.5 Turbo (Supports Claude/Gemini replacement)  
    ⚠️ For educational purposes only. Data subject to official updates.
    """)

def process_animal_query(species_name: str, region: str, api_key: str, col1, col2):
    """Process animal search query and display results"""
    with st.spinner(f"Searching for {species_name}..."):
        # 1. Fetch data from both APIs
        gbif_data = fetch_gbif_data(species_name, region)
        inat_data = fetch_inaturalist_data(species_name)
        
        # 2. Merge data
        animal_data = merge_animal_data(gbif_data, inat_data)
        if not animal_data:
            st.error(f"❌ No data found for {species_name}. Please try:")
            st.markdown("1. Use a more precise name (e.g., scientific name)")
            st.markdown("2. Remove region filter")
            st.markdown("3. Check spelling")
            return

        # 3. Generate AI explanation
        explanation = generate_curator_explanation(animal_data, api_key) if api_key else None

        # 4. Left Column: Images + Basic Info
        with col1:
            st.subheader(f"🐾 {animal_data['common_name']}", divider="red")
            st.caption(f"Scientific Name: {animal_data['scientific_name']}")
            st.caption(f"English Name: {animal_data['english_name']}")

            # Display photos
            if animal_data["photos"]:
                for idx, photo in enumerate(animal_data["photos"]):
                    st.image(
                        photo,
                        use_column_width=True,
                        caption=f"Real Photo {idx+1} (from iNaturalist)"
                    )
            else:
                st.image(
                    "https://via.placeholder.com/400x300?text=No+Photos+Available",
                    use_column_width=True,
                    caption="No Photos Available"
                )

            # Basic Info Cards
            st.divider()
            st.info(f"🌍 Distribution: {', '.join(animal_data['distribution'])}")
            st.info(f"🏕️ Habitat: {animal_data['habitat']}")
            st.info(f"🛡️ Conservation Status: {animal_data['conservation_status']}")
            st.info(f"👀 Global Observations: {animal_data['observations_count']:,} records")

            # Classification Info
            st.divider()
            st.subheader("📚 Taxonomy")
            for rank, value in animal_data["classification"].items():
                st.markdown(f"**{rank}**：{value}")

        # 5. Right Column: AI Curator Explanation
        with col2:
            st.subheader("🎤 Curator's Live Explanation", divider="blue")
            if explanation:
                st.markdown(f"<div style='font-size: 17px; line-height: 1.8;'>{explanation}</div>", unsafe_allow_html=True)
            else:
                st.warning("""
                ⚠️ Explanation not generated. Please enter a valid OpenAI API Key in the sidebar.  
                👉 If you don't have an API Key, replace the AI model in the code with free alternatives (e.g., Claude, Gemini).
                """)

if __name__ == "__main__":
    main()
