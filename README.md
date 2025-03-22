# Airports Analysis and Visualization

This repository contains code to load, process, and visualize airport data. The project performs the following tasks:

- *Data Loading & Cleaning:*  
  Loads an airports.csv file, renames columns, and updates missing timezone information using TimezoneFinder and pytz.

- *Calculations:*  
  Computes various metrics such as:
  - Euclidean distance from JFK
  - Geodesic (Haversine) distance from JFK
  - Estimated flight time (using average flight speed)
  - KMeans clustering for airport proximity

- *Visualizations:*  
  Several visualization types are provided:
  - *Scatter Plots:* Location maps (world and US), altitude-based scatter plots, and heatmaps.
  - *Route Plotting:* Plot flight routes from JFK to selected airports.
  - *Bar Charts & Histograms:* Distribution of time zones, distances, and flight times.
  - *Pie Charts:* Time zone distribution with percentage labels.
