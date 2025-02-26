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
