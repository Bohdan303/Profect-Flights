# Airports Analysis and Visualization  

This repository contains code to analyze and visualize airport data. It provides insights into airport locations, flight distances, delays, and weather impacts using Python and Dash for interactive visualizations.

## Installation  
To use this repository, install the required dependencies using pip:  
```bash
pip install pandas numpy pytz timezonefinder dash dash-bootstrap-components plotly
```
Make sure input file (if different) is a csv with the same structure as the provided airports.csv.

This repository contains code to load, process, and visualize airport data. The project performs the following tasks:

- **Data Loading & Cleaning:**  
  Loads an airports.csv file, renames columns, and updates missing timezone information using TimezoneFinder and pytz.

- **Calculations:**  
  Contains functions that:
  - Compute Euclidean distance from JFK
  - Compute Geodesic (Haversine) distance from JFK (and verifies this with the flights database)
  - Compute estimated flight time (using average flight speed)
  - KMeans clustering for airport proximity
  - Look up, store and use data to produce flights statistics for NYC airports
  - Produce statistics for flights from and to given airports
  - Produce statistics for flight delays
  - Find manufacturers with the most arrivals at a given airport
  - Compute flight speeds
  - Produce statistics on and look for relation concerning weather

- **Visualizations:**  
  Several visualization types are provided:
  - *Scatter Plots:* Location maps (world and US), altitude-based scatter plots, and heatmaps.
  - *Route Plotting:* Plot flight routes from JFK to selected airports.
  - *Bar Charts & Histograms:* Distribution of time zones, distances, and flight times.
  - *Pie Charts:* Time zone distribution with percentage labels.


__________________________________________________________________________________________________________________________


# Flight Dashboard

This project is a modular Python dashboard for monitoring NYC flight information. It is organized into three main maps:

- **data_processing**: Contains utilities and preprocessing functions for flights, airports, planes, weather, and airlines.
- **visualizations**: Contains all Plotly figures and graphs (further divided into maps, histograms, scatter plots, and airline analysis).
- **dashboard**: Contains the Streamlit dashboard application with separate tabs for each type of analysis.

## Directory Structure

```
flight_dashboard/
├── data_processing/
│   ├── utils/
│   │   ├── time_utils.py
│   │   └── db_utils.py
│   ├── preprocessing/
│   │   ├── schedule_processing.py
│   │   ├── departure_arrival.py
│   │   ├── airport_preprocessing.py
│   │   ├── flight_preprocessing.py
│   │   ├── plane_preprocessing.py
│   │   ├── weather_preprocessing.py
│   │   └── airlines_preprocessing.py
│   └── orchestration.py
├── visualizations/
│   ├── maps/
│   │   ├── world_map.py
│   │   ├── us_map.py
│   │   └── altitude_map.py
│   ├── histograms/
│   │   └── distance_histogram.py
│   ├── scatter_plots/
│   │   ├── flight_duration.py
│   │   ├── delay_vs_distance.py
│   │   └── inner_product_vs_air_time.py
│   ├── airline_analysis/
│   │   └── airline_delay.py
│   └── index.py
├── dashboard/
│   ├── tabs/
│   │   ├── general_statistics.py
│   │   ├── general_maps.py
│   │   ├── flight_routes.py
│   │   ├── distance_analysis.py
│   │   ├── flights_by_day.py
│   │   ├── trajectory_statistics.py
│   │   ├── manufacturer_airline_statistics.py
│   │   └── plane_type_analysis.py
│   └── app.py
├── main.py
├── requirements.txt
└── README.md
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the dashboard:
   ```bash
   streamlit run main.py
   ```

## Description

- **Data Processing**: Loads and preprocesses data from a SQLite database.
- **Visualizations**: Precomputes figures (maps, histograms, scatter plots, etc.) using Plotly.
- **Dashboard**: Provides an interactive Streamlit UI for exploring flight data.
