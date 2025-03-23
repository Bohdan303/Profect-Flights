import os
import sqlite3
import streamlit as st
from data_processing.utils.db_utils import load_data, save_preprocessed_data
from data_processing.orchestration import preprocess_data
from visualizations.index import create_all_visualizations
from dashboard.app import run_dashboard
import pandas as pd
import zipfile

def load_preprocessed_data(preprocessed_db):
    conn = sqlite3.connect(preprocessed_db)
    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
    df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
    df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
    df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)
    return df_airports, df_flights, df_planes, df_weather, df_airlines

def unzip_preprocessed_db(zip_path="preprocessed_flights.zip", extract_to="./"):
    """
    Unzips the preprocessed database file if not already extracted.
    """
    db_path = os.path.join(extract_to, "preprocessed_flights.db")
    
    if not os.path.exists(db_path):
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            print(f"Preprocessed DB extracted to {extract_to}")
        else:
            print("No preprocessed DB zip found.")
    else:
        print("Preprocessed DB already extracted.")
    
    return db_path


if __name__ == "__main__":
    conn, df_airports, df_flights, df_planes, df_weather, df_airlines = load_data()
    preprocessed_db = "preprocessed_flights.db"
    preprocessed_zip = "preprocessed_flights.zip"
    preprocessed_db = "preprocessed_flights.db"
    unzip_preprocessed_db(preprocessed_zip)
    
    if os.path.exists(preprocessed_db):
        st.write("Loading preprocessed data from", preprocessed_db)
        df_airports, df_flights, df_planes, df_weather, df_airlines = load_preprocessed_data(preprocessed_db)
    else:
        df_airports, df_flights, df_planes, df_weather, df_airlines = preprocess_data(conn, df_airports, df_flights, df_planes, df_weather, df_airlines)
        save_preprocessed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
    visuals = create_all_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
    run_dashboard(df_airports, df_flights, df_planes, df_weather, df_airlines, conn, visuals)
