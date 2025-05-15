# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.request, json

# ── 0) Page config & theming ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Canada CAT‐Event Severity",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    /* hide Streamlit footer & header for a cleaner look */
    footer 
    header 
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 1) Header + instructions ─────────────────────────────────────────────────
st.title("📊 Average Loss per CAT Event in Canada")
with st.expander("ℹ️ How it works", expanded=False):
    st.markdown("""
    1. Select one or more **preloaded datasets**.  
    2. Filter the years you want to include.  
    3. View an interactive choropleth of **average loss per event** by province.
    """)

# ── 2) Preload CSVs ────────────────────────────────────────────────────────────
@st.cache_data
def load_all_csvs():
    return {
        "FL Losses": pd.read_csv("Quantify Case Competition 2025 Case Data FL.csv"),
        "HL Losses": pd.read_csv("Quantify Case Competition 2025 Case Data HL.csv"),
        "FI Losses": pd.read_csv("Quantify Case Competition 2025 Case Data FI.csv"),
        "WS Losses": pd.read_csv("Quantify Case Competition 2025 Case Data WS.csv"),
    }

all_dfs = load_all_csvs()

# ── 3) Let user pick which dataset(s) ───────────────────────────────────────────
choices = st.sidebar.multiselect(
    "Select dataset(s) to include", 
    options=list(all_dfs.keys()), 
    default=list(all_dfs.keys())[:1]
)
if not choices:
    st.sidebar.warning("Please select at least one dataset.")
    st.stop()

# pull out the DataFrames the user selected
df_list = [all_dfs[name] for name in choices]

# ── 4) Load & validate selected dfs ────────────────────────────────────────────
@st.cache_data
def prep(df_list):
    out = []
    for df in df_list:
        for col in ["Provinces", "Event_year", "Total_losses_in_billions"]:
            if col not in df.columns:
                st.error(f"Missing `{col}` in one of your preloaded CSVs")
                st.stop()
        out.append(
            df[["Provinces","Event_year","Total_losses_in_billions"]]
              .rename(columns={
                  "Event_year":"Year",
                  "Total_losses_in_billions":"Loss"
              })
        )
    return pd.concat(out, ignore_index=True)

df = prep(df_list)

# ── 5) Year filter ────────────────────────────────────────────────────────────
years = sorted(df["Year"].dropna().unique().astype(int))
st.sidebar.markdown("### Filter by year")
keep = [y for y in years if st.sidebar.checkbox(str(y), value=True)]
df = df[df["Year"].isin(keep)]
# st.markdown(f"**Records:** {len(df):,}  **Years:** {keep}")
if df.empty:
    st.warning("No data after filtering—try different years.")
    st.stop()

# ── 6) Region→Province ISO mapping ────────────────────────────────────────────
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

# 7) Aggregate
prov_sum = (
    df_exp
    .groupby("ISO", as_index=False)
    .agg(TotalLoss=("Loss","sum"))
)

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

# 8) Aggregate: sum losses & count events
prov_summary = (
    df_exp
    .groupby("ISO", as_index=False)
    .agg(
        TotalLoss   = ("Loss",  "sum"),
        EventCount  = ("Loss",  "count")
    )
)

# 9) Compute severity = total loss / number of events
prov_summary["Severity"] = prov_summary["TotalLoss"] / prov_summary["EventCount"]

# map CA-XX → full name (same as before)
prov_summary["prov_name"] = prov_summary["ISO"].map(iso_to_name)

# sanity-check
missing = prov_summary[prov_summary["prov_name"].isna()]
if not missing.empty:
    st.error("Missing mapping for: " + ", ".join(missing["ISO"].unique()))
    st.stop()

# 9.1) Summary metrics
col1, col2, col3 = st.columns(3)
col1.metric("📆 Years", f"{min(keep)} – {max(keep)}")
col2.metric("🔢 Total Events", f"{int(prov_summary['EventCount'].sum()):,}")
col3.metric("💸 Avg. Severity", f"{prov_summary['Severity'].mean():.2f} billion")

# 10) Load Canada GeoJSON
@st.cache_data
def get_geojson():
    url = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/master/public/data/canada.geojson"
    with urllib.request.urlopen(url) as r:
        return json.load(r)

can_geo = get_geojson()

# 11) Plot choropleth of severity
fig = px.choropleth_mapbox(
    prov_summary,
    geojson=can_geo,
    locations="prov_name",              # province names
    featureidkey="properties.name",     # match GeoJSON “name”
    color="Severity",                   # ← now using Severity
    color_continuous_scale="YlOrRd",
    mapbox_style="carto-positron",
    zoom=2.2,
    center={"lat":56.13, "lon":-106.35},
    opacity=0.6,
    labels={"Severity":"Loss per Event (billion)"}
)
fig.update_layout(
    margin={"r":0,"t":30,"l":0,"b":0},
    title="Average Loss per CAT Event by Province"
)
st.plotly_chart(fig, use_container_width=True)
