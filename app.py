import streamlit as st
import pandas as pd
import plotly.express as px
import wbgapi as wb  # The correct, working library
from datetime import datetime
from json import JSONDecodeError  # To catch specific API errors

# --- 1. App Configuration ---
# Set the page to be wide, add a title and icon
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
# Keys = Readable Names, Values = World Bank API Codes
# BUG FIX: NameError: INDICATORSDB -> INDICATORS_DB (fixed)
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
# Create a list of just the names for the dropdown
indicator_names = list(INDICATORS_DB.keys())

# --- Caching Functions (for performance) ---
# @st.cache_data tells Streamlit to run this function only once and save the result.
@st.cache_data
def get_countries():
    """
    Fetches and formats a list of countries and their codes from wbgapi.
    BUG FIX: AttributeError: get_country/search_countries -> wb.economy.list() (fixed)
    """
    countries = wb.economy.list()
    
    # Filter out regions or aggregates (like "World", "Euro Area")
    countries = [country for country in countries if country.get('region') != "Aggregates"]

    # Get a list of just the names
    country_names = [country['value'] for country in countries]
    
    # Create a mapping of country name to its 3-letter code (e.g., "India": "IND")
    country_codes = {country['value']: country['id'] for country in countries}
    return country_names, country_codes

@st.cache_data
def get_data(country_code, data_date_range, indicators_dict):
    """
    Fetches data from the World Bank API using wbgapi.
    This is the robust version that fixes all previous data-related bugs.
    """
    try:
        # Get the API codes from our indicator dictionary (e.g., ['NY.GDP.PCAP.CD', ...])
        indicator_codes = list(indicators_dict.values())
        
        # --- BUG FIX (v8) ---
        # This fixes JSONDecodeError and Resource not found.
        # We convert the range() object into a safe, explicit list of strings:
        # e.g., ['2000', '2001', '2002', ..., '2023']
        # The API cannot misinterpret this.
        time_list = [str(year) for year in data_date_range]
        
        df_wide = wb.data.DataFrame(
            indicator_codes,
            country_code,
            time=time_list  # Use the safe list of strings
        )

        # --- Data Processing Pipeline ---
        
        # 1. Reset index. This turns the MultiIndex (country, time) into columns.
        df_wide = df_wide.reset_index()

        # 2. ROBUSTLY rename the first two columns.
        # BUG FIX: KeyError: [economy] -> This logic is now robust (fixed)
        # We don't assume names; we just take the first two columns.
        rename_map = {
            df_wide.columns[0]: 'Country',
            df_wide.columns[1]: 'TimeStr'  # e.g., 'YR2000'
        }
        df_wide = df_wide.rename(columns=rename_map)

        # 3. "Melt" the DataFrame from wide to long format.
        df_long = df_wide.melt(
            id_vars=['Country', 'TimeStr'],
            var_name='series',  # This column will have the API codes
            value_name='Value'  # This column will have the data
        )
        
        # 4. Clean the 'Year' column (e.g., 'YR2000' -> 2000)
        df_long['Year'] = df_long['TimeStr'].str.replace('YR', '').astype(int)
        
        # 5. "Pivot" the table to get indicators back as columns.
        df_final = df_long.pivot(
            index=['Country', 'Year'],
            columns='series',
            values='Value'
        ).reset_index()

        # 6. Rename indicator columns from codes back to readable names
        reverse_indicator_map = {v: k for k, v in indicators_dict.items()}
        df_final = df_final.rename(columns=reverse_indicator_map)
        
        # Return the clean data and no error
        return df_final.sort_values('Year'), None
    
    except JSONDecodeError as e:
        # Catch the specific error if the API sends bad JSON
        return None, (
            "JSONDecodeError: The World Bank API sent back a broken response. "
            "This can happen if the API is temporarily down. "
            f"Details: {e}"
        )
    except Exception as e:
        # Catch all other errors (e.g., "Resource not found")
        return None, str(e)

# --- 4. Sidebar Widget Implementation ---
# Load the country list (this will be cached after the first run)
country_names, country_codes = get_countries()
current_year = datetime.now().year

# Set "India" as the default selection
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
    index=0  # Default to 'GDP per capita'
)

indicator_2_name = st.sidebar.selectbox(
    "Select Indicator 2 (Trend 2 & Correlation Y-axis)",
    indicator_names,
    index=1  # Default to 'Female Literacy Rate'
)

# Year range slider
start_year, end_year = st.sidebar.slider(
    "Select Year Range",
    1990,                # Min year
    current_year,        # Max year
    (2000, current_year - 1) # Default range
)

# --- 5. Data Fetching and Analysis ---
# Stop the app if the user hasn't selected a valid country
if selected_country_name not in country_codes:
    st.error("Please select a valid country from the list.")
    st.stop()

# Get the 3-letter code for the selected country
country_code = country_codes[selected_country_name]

# Create the dictionary of only the two indicators we want to fetch
indicators_to_fetch = {
    indicator_1_name: INDICATORS_DB[indicator_1_name],
    indicator_2_name: INDICATORS_DB[indicator_2_name]
}

# We create the safe range() object to pass to our function
data_date_range = range(start_year, end_year + 1)

# Call the data fetching function
data, error = get_data(country_code, data_date_range, indicators_to_fetch)

# --- 6. Main Page Display (Charts and Data) ---

# First, check if the 'error' variable contains anything.
if error:
    st.error(
        f"Could not fetch data for {selected_country_name}. "
        f"Error details: {error}"
    )
# Next, check if the data is empty (this is not an error)
elif data is None or data.empty:
    st.warning(f"No data found for {selected_country_name} for these indicators in this year range.")
# If no errors and data is not empty, show the charts!
else:
    st.header(f"Analysis for {selected_country_name} ({start_year} - {end_year})")

    # Create two columns for the trend charts
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
        
    # Create the correlation plot
    st.header("Correlation Analysis")
    st.write(f"Is there a link between '{indicator_1_name}' and '{indicator_2_name}'?")
    
    # Prep data: drop any rows where EITHER indicator is missing
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
        # This is a safe fallback, not an error
        st.warning("Not enough overlapping data to show a correlation for these years.")
    
    # Add an expander to show the raw data table
    with st.expander("Show Raw Data Table"):
        st.dataframe(data)
