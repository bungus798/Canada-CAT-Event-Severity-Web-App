# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.request, json

st.set_page_config(layout="wide")
st.title("📊 Canada Losses by Province (from your Case CSVs)")
st.markdown(
    """
    1. Upload one or more of your **Case Data** CSVs (they must have columns `Provinces`, `Event_year`, `Total_losses_in_billions`).  
    2. Pick which years to include via the sidebar checkboxes.  
    3. See a province-level choropleth of summed losses.
    """
)

# 1) File upload
files = st.sidebar.file_uploader(
    "Upload CSVs", type="csv", accept_multiple_files=True
)
if not files:
    st.sidebar.info("Please upload at least one CSV.")
    st.stop()

# 2) Load & validate
@st.cache_data
def load_csvs(flist):
    df_list = []
    for f in flist:
        df = pd.read_csv(f)
        # required cols
        for col in ["Provinces","Event_year","Total_losses_in_billions"]:
            if col not in df.columns:
                st.error(f"Missing `{col}` in {f.name}")
                st.stop()
        df_list.append(df[["Provinces","Event_year","Total_losses_in_billions"]]
                       .rename(columns={
                           "Event_year":"Year",
                           "Total_losses_in_billions":"Loss"
                       }))
    return pd.concat(df_list, ignore_index=True)

df = load_csvs(files)

# 3) Year filter
years = sorted(df["Year"].dropna().unique().astype(int))
st.sidebar.markdown("### Filter by year")
keep = [y for y in years if st.sidebar.checkbox(str(y), value=True)]
df = df[df["Year"].isin(keep)]
st.markdown(f"**Records:** {len(df):,}  **Years:** {keep}")

if df.empty:
    st.warning("No data after filtering—try different years.")
    st.stop()

# 4) Region→Province ISO mapping
region_map = {
    # single provinces
    "ON": ["CA-ON"], "QC": ["CA-QC"], "BC": ["CA-BC"], "AB": ["CA-AB"],
    "SK": ["CA-SK"], "MB": ["CA-MB"], "NB": ["CA-NB"], "NS": ["CA-NS"],
    "PE": ["CA-PE"], "NL": ["CA-NL"], "YT": ["CA-YT"], "NT": ["CA-NT"],
    "NU": ["CA-NU"],
    # grouped regions
    "Maritimes": ["CA-NB","CA-NS","CA-PE"],
    "Priaries":  ["CA-AB","CA-SK","CA-MB"],   # matches your CSV’s “Priaries”
    "Prairies": ["CA-AB","CA-SK","CA-MB"],   # in case of correct spelling
    "Priaires": ["CA-AB","CA-SK","CA-MB"], 
    "Praries": ["CA-AB","CA-SK","CA-MB"], 
    "Praires": ["CA-AB","CA-SK","CA-MB"], 
}

def split_to_iso(s):
    parts = [p.strip() for p in str(s).split(",")]
    out = []
    for p in parts:
        if p in region_map:
            out.extend(region_map[p])
        else:
            st.error(f"Unknown region/province “{p}” – please adjust `region_map`.")
            st.stop()
    return out

df["ISO"] = df["Provinces"].apply(split_to_iso)
df_exp = df.explode("ISO")

# 5) Aggregate
prov_sum = (
    df_exp
    .groupby("ISO", as_index=False)
    .agg(TotalLoss=("Loss","sum"))
)

st.dataframe(prov_sum)


# map CA-XX → full name
iso_to_name = {
    "CA-ON":"Ontario",
    "CA-QC":"Quebec",
    "CA-NS":"Nova Scotia",
    "CA-NB":"New Brunswick",
    "CA-MB":"Manitoba",
    "CA-BC":"British Columbia",
    "CA-PE":"Prince Edward Island",
    "CA-SK":"Saskatchewan",
    "CA-AB":"Alberta",
    "CA-NL":"Newfoundland and Labrador",
    "CA-NT":"Northwest Territories",
    "CA-YT":"Yukon",
    "CA-NU":"Nunavut",
}

# create a column with the exact names
prov_sum["prov_name"] = prov_sum["ISO"].map(iso_to_name)

# sanity-check that you got them all
missing = prov_sum[prov_sum["prov_name"].isna()]
if not missing.empty:
    st.error("Missing mapping for: " + ", ".join(missing["ISO"].unique()))
    st.stop()


# 6) Load Canada GeoJSON
@st.cache_data
def get_geojson():
    url = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/master/public/data/canada.geojson"
    with urllib.request.urlopen(url) as r:
        return json.load(r)

can_geo = get_geojson()
st.write("▶️ GeoJSON province names:", 
         [feat["properties"]["name"] for feat in can_geo["features"]])
st.write("🔍 First feature properties:", can_geo["features"][0]["properties"])
st.write("🔍 All property keys:", list(can_geo["features"][0]["properties"].keys()))

# 7) Plot choropleth
fig = px.choropleth_mapbox(
    prov_sum,
    geojson=can_geo,
    locations="prov_name",              # use your mapped names
    featureidkey="properties.name",     # match the "name" field in the GeoJSON
    color="TotalLoss",
    color_continuous_scale="YlOrRd",
    mapbox_style="carto-positron",
    zoom=3.5,
    center={"lat":56.13, "lon":-106.35},
    opacity=0.6,
    labels={"TotalLoss":"Loss (billions)"}
)
fig.update_layout(margin={"r":0,"t":30,"l":0,"b":0},
                  title="Total Loss by Province")
st.plotly_chart(fig, use_container_width=True)
