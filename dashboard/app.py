import streamlit as st
from dashboard.tabs import (
    general_statistics,
    general_maps,
    flight_routes,
    distance_analysis,
    flights_by_day,
    trajectory_statistics,
    manufacturer_airline_statistics,
    plane_type_analysis
)

def run_dashboard(df_airports, df_flights, df_planes, df_weather, df_airlines, conn, visuals):
    st.title("Flights Dashboard")
    tab = st.sidebar.radio(
        "Select Tab",
        options=["General Statistics", "General Maps", "Flight Routes", "Distance Analysis", 
                 "Flights by Day", "Trajectory Statistics", "Manufacturer & Airline Statistics", "Plane Type Analysis"]
    )
    if tab == "General Statistics":
        general_statistics.render(df_airports, df_flights, visuals)
    elif tab == "General Maps":
        general_maps.render(df_airports, visuals)
    elif tab == "Flight Routes":
        flight_routes.render(df_airports, df_flights)
    elif tab == "Distance Analysis":
        distance_analysis.render(df_flights, visuals)
    elif tab == "Flights by Day":
        flights_by_day.render(df_airports, df_flights)
    elif tab == "Trajectory Statistics":
        trajectory_statistics.render(df_airports, df_flights, df_planes)
    elif tab == "Manufacturer & Airline Statistics":
        manufacturer_airline_statistics.render(df_airports, df_flights, df_airlines,visuals)
    elif tab == "Plane Type Analysis":
        plane_type_analysis.render(df_airports, df_flights, df_planes, visuals)
