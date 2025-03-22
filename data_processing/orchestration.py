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

def preprocess_data(conn, df_airports, df_flights, df_planes, df_weather, df_airlines):
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
    
    # Example: compute local arrival if desired (not fully detailed here)
    # from data_processing.preprocessing.flight_preprocessing import compute_local_arrival
    # df_flights = compute_local_arrival(df_flights, df_airports)
    
    tables = {"airports": df_airports, "flights": df_flights, "planes": df_planes, "weather": df_weather, "airlines": df_airlines}
    print_missing_values(tables)
    return df_airports, df_flights, df_planes, df_weather, df_airlines
