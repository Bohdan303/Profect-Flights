import os
import sqlite3
import pandas as pd
   
def load_data(db_path="processed_flights.db"):
    conn = sqlite3.connect(db_path)
    
    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
    df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
    df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
    df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)
    conn.close()
    
    return df_airports, df_flights, df_planes, df_weather, df_airlines

def save_preprocessed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, output_db="preprocessed_flights.db"):
    new_conn = sqlite3.connect(output_db)
    df_airports.to_sql("airports", new_conn, if_exists="replace", index=False)
    df_flights.to_sql("flights", new_conn, if_exists="replace", index=False)
    df_planes.to_sql("planes", new_conn, if_exists="replace", index=False)
    df_weather.to_sql("weather", new_conn, if_exists="replace", index=False)
    df_airlines.to_sql("airlines", new_conn, if_exists="replace", index=False)
    new_conn.commit()
    new_conn.close()
    print("Preprocessed data saved to", output_db)
    
def save_processed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, output_db="processed_flights.db"):
    new_conn = sqlite3.connect(output_db)
    df_airports.to_sql("airports", new_conn, if_exists="replace", index=False)
    df_flights.to_sql("flights", new_conn, if_exists="replace", index=False)
    df_planes.to_sql("planes", new_conn, if_exists="replace", index=False)
    df_weather.to_sql("weather", new_conn, if_exists="replace", index=False)
    df_airlines.to_sql("airlines", new_conn, if_exists="replace", index=False)
    new_conn.commit()
    new_conn.close()
    print("Processed data saved to", output_db)

