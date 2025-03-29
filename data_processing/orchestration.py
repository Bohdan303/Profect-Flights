import sqlite3
import pandas as pd

def print_missing_values(tables):
    for table_name, df in tables.items():
        missing_columns = df.columns[df.isnull().any()]
        if not missing_columns.empty:
            print(f"Table '{table_name}' has missing values in:")
            for col in missing_columns:
                print(f"  - {col}: {df[col].isnull().sum()} missing")
            print()
        else:
            print(f"Table '{table_name}' has no missing values.\n")

def preprocess_data(df_airports, df_flights, df_planes, df_weather, df_airlines):
    from data_processing.preprocessing.airlines_preprocessing import preprocess_airlines
    from data_processing.preprocessing.airport_preprocessing import preprocess_airports
    from data_processing.preprocessing.flight_preprocessing import preprocess_flights, compute_flight_distances  # if needed elsewhere
    from data_processing.preprocessing.plane_preprocessing import preprocess_planes
    from data_processing.preprocessing.weather_preprocessing import preprocess_weather, analyze_weather_effects, preprocess_weather
    
    df_airlines = preprocess_airlines(df_airlines)
    print("Missing values in airlines data:\n", df_airlines.isnull().sum())
    df_airports = preprocess_airports(df_airports, df_flights)
    print("Missing values in airports data:\n", df_airports.isnull().sum())
    df_flights = preprocess_flights(df_flights, df_airports)
    print("Missing values in flights data:\n", df_flights.isnull().sum())
    df_planes = preprocess_planes(df_planes, df_flights)
    print("Missing values in planes data:\n", df_planes.isnull().sum())
    df_weather = preprocess_weather(df_weather, df_airports)
    print("Missing values in weather data:\n", df_weather.isnull().sum())
    
    weather_analysis = analyze_weather_effects(df_flights, df_weather)
    print("Weather Analysis by Month:\n", weather_analysis)

    print("Dropping unnecessary columns...")
    df_weather = df_weather.drop(columns=["dewp", "humid", "wind_gust", "pressure", "visib", "temp","lat"], axis=1)
    df_flights = df_flights.drop(columns=["year","month","day","sched_dep_time","sched_arr_time","arr_time","dep_time","base_date","sched_dep_dt","sched_arr_dt","computed_sched_air_time"], axis=1)
    
    tables = {"airports": df_airports, "flights": df_flights, "planes": df_planes, "weather": df_weather, "airlines": df_airlines}
    print_missing_values(tables)
    return df_airports, df_flights, df_planes, df_weather, df_airlines

def create_processed_data_file(db_path= "flights_database.db", output_db="processed_flights.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = 100000")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_dest ON flights(dest)")
    conn.commit()
    
    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
    df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
    df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
    df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)
    conn.close()
    
    new_conn = sqlite3.connect(output_db)
    df_airports.to_sql("airports", new_conn, if_exists="replace", index=False)
    df_flights.to_sql("flights", new_conn, if_exists="replace", index=False)
    df_planes.to_sql("planes", new_conn, if_exists="replace", index=False)
    df_weather.to_sql("weather", new_conn, if_exists="replace", index=False)
    df_airlines.to_sql("airlines", new_conn, if_exists="replace", index=False)
    new_conn.commit()
    new_conn.close()
    print("Loaded data from flights_database.db and saved it to", output_db)
    


