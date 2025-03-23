import os
import sqlite3
import streamlit as st
from data_processing.utils.db_utils import load_data, save_preprocessed_data
from data_processing.orchestration import preprocess_data
from visualizations.index import create_all_visualizations
from dashboard.app import run_dashboard
import pandas as pd

def load_preprocessed_data(preprocessed_db):
    conn = sqlite3.connect(preprocessed_db)
    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
    df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
    df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
    df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)
    return df_airports, df_flights, df_planes, df_weather, df_airlines

    
if __name__ == "__main__":
    conn, df_airports, df_flights, df_planes, df_weather, df_airlines = load_data()
    preprocessed_db = "preprocessed_flights.db"
    
    if os.path.exists(preprocessed_db):
        st.write("Loading preprocessed data from", preprocessed_db)
        df_airports, df_flights, df_planes, df_weather, df_airlines = load_preprocessed_data(preprocessed_db)
    else:
        df_airports, df_flights, df_planes, df_weather, df_airlines = preprocess_data(conn, df_airports, df_flights, df_planes, df_weather, df_airlines)
        save_preprocessed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
    visuals = create_all_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
    run_dashboard(df_airports, df_flights, df_planes, df_weather, df_airlines, conn, visuals)
