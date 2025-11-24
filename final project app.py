import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

# 假设数据文件路径
DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/unesco_ich.json")

@st.cache_data
def load_data():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # 假设 data 是 list of dicts
    df = pd.json_normalize(data)
    return df

def main():
    st.title("Global Intangible Cultural Heritage Explorer")

    df = load_data()
    country_list = sorted(df['countries'].explode().unique())
    selected_country = st.selectbox("按国家筛选", ["全部"] + country_list)
    if selected_country != "全部":
        df = df[df['countries'].apply(lambda lst: selected_country in lst)]

    year_min, year_max = int(df['year_inscribed'].min()), int(df['year_inscribed'].max())
    years = st.slider("入选年份范围", year_min, year_max, (year_min, year_max))

    df = df[(df['year_inscribed'] >= years[0]) & (df['year_inscribed'] <= years[1])]

    st.write(f"共 {len(df)} 项符合条件")

    # 地图展示（假设有 lat/lon 字段）
    if 'latitude' in df.columns and 'longitude' in df.columns:
        fig = px.scatter_geo(df,
                             lat='latitude', lon='longitude',
                             hover_name='name_en',
                             hover_data=['countries','year_inscribed'])
        fig.update_layout(height=500, margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig, use_container_width=True)

    # 列表展示
    for _, row in df.iterrows():
        st.markdown(f"### {row['name_en']} — {', '.join(row['countries'])}")
        st.write(f"入选年份：{row['year_inscribed']}")
        st.write(row.get('short_description_en', '无简介'))
        st.write("---")

if __name__ == "__main__":
    main()

