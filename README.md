**Airports Analysis and Visualization**

This repository contains tools to analyze and visualize airport data. It provides insights into airport locations, flight distances, delays, weather impacts and scheduling trends. The project uses Python,Pandas, Plotly, and Streamlit for data analysis and visualizations.

**Installation**

To use this repository, install the required dependencies using pip:
```bash
pip install pandas numpy plotly streamlit pytz timezonefinder reverse_geocoder pycountry pycountry_convert requests threading concurrent math time datetime sqlite3
```
Make sure input file (if different) is with the same structure as the provided flights_database.zip.

This repository contains code to load, process, and visualize airport data. The project performs the following tasks:

**Data Loading & Cleaning:**

Loads airport and flight data from databases.

Cleans missing values and updates timezone information using TimezoneFinder and pytz.

Computes Haversine distances and flight bearings.

**Calculations:**

*1. Flight Time Computation & Analysis*

Converts scheduled and actual departure times to UTC.

Identifies flight delays and calculates air time.

Adjusts for overnight flights and timezone differences.

*2. Weather Data Integration Fetches and processes historical weather data.*

Merges weather data with airport and flight records.

Analyzes how weather conditions impact flight schedules and delays.

*3. Parallel Processing for Performance*

Uses ThreadPoolExecutor and ProcessPoolExecutor to speed up computations.

Efficiently processes large datasets in parallel for faster insights.

*4. Interactive Dashboard (Streamlit)*

View real-time visualizations of flight statistics and weather impacts.

Analyze delays, flight speeds, and manufacturer-specific trends.

Explore geographical flight patterns using interactive maps.

*Visualizations:*

Several visualization types are provided:

- Scatter Plots: Location maps (world and US), altitude-based scatter plots, and heatmaps.
- Route Plotting: Visualizing flight paths from JFK and other airports.
- Bar Charts & Histograms: Analyzing flight delays, time zone distributions, and speeds.
- Pie Charts: Time zone distribution with percentage labels.
- Weather Analysis Charts: Evaluating flight performance under different weather conditions.

*Usage:*

To run the Streamlit dashboard:

```bash
streamlit run "main.py"
```

This will launch an interactive web interface where users can explore flight statistics.

*Directory Structure* 
```bash
flight_dashboard/
├── data_processing/
│   ├── __init__.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── time_utils.py
│   │   └── db_utils.py
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── schedule_processing.py
│   │   ├── departure_arrival.py
│   │   ├── airport_preprocessing.py
│   │   ├── flight_preprocessing.py
│   │   ├── plane_preprocessing.py
│   │   ├── weather_preprocessing.py
│   │   └── airlines_preprocessing.py
│   └── orchestration.py
│
├── visualizations/
│   ├── __init__.py
│   ├── maps/
│   │   ├── __init__.py
│   │   ├── world_map.py
│   │   ├── us_map.py
│   │   └── altitude_map.py
│   ├── histograms/
│   │   ├── __init__.py
│   │   └── distance_histogram.py
│   ├── scatter_plots/
│   │   ├── __init__.py
│   │   ├── flight_duration.py
│   │   ├── delay_vs_distance.py
│   │   └── inner_product_vs_air_time.py
│   ├── airline_analysis/
│   │   ├── __init__.py
│   │   └── airline_delay.py
│   └── index.py
│
├── dashboard/
│   ├── __init__.py
│   ├── tabs/
│   │   ├── __init__.py
│   │   ├── general_statistics.py
│   │   ├── general_maps.py
│   │   ├── flight_routes.py
│   │   ├── distance_analysis.py
│   │   ├── flights_by_day.py
│   │   ├── trajectory_statistics.py
│   │   ├── manufacturer_airline_statistics.py
│   │   └── plane_type_analysis.py
│   └── app.py
│
├── main.py
├── requirements.txt
└── README.md
```
