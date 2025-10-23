import streamlit as st
import pandas as pd
import plotly.express as px
import wbgapi as wb
from datetime import datetime

# --- 1. App Configuration ---
st.set_page_config(
    page_title="Socio-Economic Dashboard",
    page_icon="📈",
    layout="wide"
)

# --- 2. Title and Introduction ---
st.title("📈 Socio-Economic Insights Dashboard")
st.write(
    "An interactive tool to analyze and correlate data from the World Bank. "
    "Select a country, two indicators, and a year range to begin."
)

# --- 3. Sidebar (User Controls) ---
st.sidebar.header("Dashboard Controls")

# Define the indicators you want to offer in a dictionary
INDICATORS_DB = {
    "GDP per capita (current US$)": "NY.GDP.PCAP.CD",
    "Female Literacy Rate (% ages 15+)": "SE.PRM.LITR.FE.ZS",
    "Population, total": "SP.POP.TOTL",
    "Unemployment, total (% of total labor force)": "SL.UEM.TOTL.ZS",
    "Infant mortality rate (per 1,000 live births)": "SP.DYN.IMRT.IN",
    "Life expectancy at birth, total (years)": "SP.DYN.LE00.IN",
    "Access to electricity (% of population)": "EG.ELC.ACCS.ZS",
    "CO2 emissions (metric tons per capita)": "EN.ATM.CO2E.PC"
}
indicator_names = list(INDICATORS_DB.keys())

# --- Caching Functions (for performance) ---
@st.cache_data
def get_countries():
    """Fetches and formats a list of countries and their codes from wbgapi."""
    
    # wb.economy.list() gets all economies (countries and regions)
    countries = wb.economy.list()

    # Filter out regions or aggregates that aren't countries
    countries = [country for country in countries if country.get('region') != "Aggregates"]

    country_names = [country['value'] for country in countries]
    # Create a mapping of country name to its 3-letter code (e.g., "India": "IND")
    country_codes = {country['value']: country['id'] for country in countries}
    return country_names, country_codes

@st.cache_data
def get_data(country_code, data_date_range, indicators_dict):
    """
    Fetches data from the World Bank API using wbgapi.
    """
    try:
        # Get the API codes from our indicator dictionary
        indicator_codes = list(indicators_dict.values())
        
        # wbgapi returns data in a "wide" format, so we must process it
        df_wide = wb.data.DataFrame(
            indicator_codes,
            country_code,
            time=data_date_range
        )

        # --- Data Processing to make it usable ---
        # 1. Reset index to get 'economy' and 'time' as columns
        df_wide = df_wide.reset_index()
        
        # 2. "Melt" the DataFrame from wide to long format
        df_long = df_wide.melt(id_vars=['economy', 'series'], var_name='Year', value_name='Value')
        
        # 3. Clean the 'Year' column (e.g., 'YR2000' -> 2000)
        df_long['Year'] = df_long['Year'].str.replace('YR', '').astype(int)
        
        # 4. "Pivot" the table to get indicators as columns
        df_final = df_long.pivot(
            index=['economy', 'Year'],
            columns='series',
            values='Value'
        ).reset_index()

        # Rename columns from API codes to readable names
        reverse_indicator_map = {v: k for k, v in indicators_dict.items()}
        df_final = df_final.rename(columns=reverse_indicator_map)
        
        return df_final.sort_values('Year'), None  # Return data and no error
        
    except Exception as e:
        # Return no data and the error message
        return None, str(e)

# --- 4. Sidebar Widget Implementation ---
country_names, country_codes = get_countries()
current_year = datetime.now().year

# Find the index for 'India' to set as default.
try:
    default_country_index = country_names.index("India")
except ValueError:
    default_country_index = 0  # Default to first country if India isn't found
    
selected_country_name = st.sidebar.selectbox(
    "Select a Country",
    country_names,
    index=default_country_index
)

indicator_1_name = st.sidebar.selectbox(
    "Select Indicator 1 (Trend 1 & Correlation X-axis)",
    indicator_names,
    index=0
)

indicator_2_name = st.sidebar.selectbox(
    "Select Indicator 2 (Trend 2 & Correlation Y-axis)",
    indicator_names,
    index=1
)

start_year, end_year = st.sidebar.slider(
    "Select Year Range",
    1990,
    current_year,
    (2000, current_year - 1)
)

# --- 5. Data Fetching and Analysis ---
if selected_country_name not in country_codes:
    st.error("Please select a valid country from the list.")
    st.stop()

country_code = country_codes[selected_country_name]

# Create the dictionary of only the indicators we want to fetch
indicators_to_fetch = {
    indicator_1_name: INDICATORSDB[indicator_1_name],
    indicator_2_name: INDICATORS_DB[indicator_2_name]
}

# Create the date range (e.g., range(2000, 2024))
data_date_range = range(start_year, end_year + 1)

# Call the data fetching function
data, error = get_data(country_code, data_date_range, indicators_to_fetch)

# --- 6. Main Page Display (Charts and Data) ---
if error:
    st.error(
        f"Could not fetch data for {selected_country_name}. "
        f"Error details: {error}"
    )
elif data is None or data.empty:
    st.warning("No data found for the selected country, indicators, and year range.")
else:
    st.header(f"Analysis for {selected_country_name} ({start_year} - {end_year})")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"Trend: {indicator_1_name}")
        fig1 = px.line(
            data,
            x='Year',
            y=indicator_1_name,
            title=f"{indicator_1_name} Over Time"
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.subheader(f"Trend: {indicator_2_name}")
        fig2 = px.line(
            data,
            x='Year',
            y=indicator_2_name,
            title=f"{indicator_2_name} Over Time"
        )
        st.plotly_chart(fig2, use_container_width=True)
        
    st.header("Correlation Analysis")
    st.write(f"Is there a link between '{indicator_1_name}' and '{indicator_2_name}'?")
    
    # Drop rows where either indicator has missing data (NaN)
    corr_data = data[[indicator_1_name, indicator_2_name]].dropna()
    
    if not corr_data.empty:
        fig3 = px.scatter(
            corr_data,
            x=indicator_1_name,
            y=indicator_2_name,
            title=f"Correlation Plot",
            trendline="ols"  # 'ols' adds a regression line
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("Not enough overlapping data to show a correlation for these years.")
    
    with st.expander("Show Raw Data Table"):
        st.dataframe(data)
