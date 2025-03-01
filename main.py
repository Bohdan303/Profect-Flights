import os  
import sqlite3  
import pickle  
import datetime  
import time  
from math import radians, sin, cos, sqrt, atan2  
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor  
import concurrent

import pandas as pd  
import numpy as np  
import pytz  
from timezonefinder import TimezoneFinder  
import reverse_geocoder as rg  
import pycountry  
import pycountry_convert as pc  
import requests

import plotly.express as px  
import plotly.graph_objects as go

# ============================================================================  
# Part 1: Data Loading and Preprocessing  
# ============================================================================  

# Global Objects and Constants  
tf = TimezoneFinder()  
BASE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"  
HOURLY_PARAMS = ("temperature_2m,dewpoint_2m,relativehumidity_2m,"  
                 "winddirection_10m,windspeed_10m,windgusts_10m,"  
                 "precipitation,surface_pressure,visibility")

# --- Time Utilities ---  
def convert_time_hour_to_utc(ts):  
    """Converts a Unix timestamp (in seconds) to a UTC-aware datetime."""  
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

def clock_to_minutes(val):  
    """Converts a HHMM clock value to minutes since midnight."""  
    try:  
        val_int = int(val)  
    except Exception:  
        return None  
    s = f"{val_int:04d}"  
    hours = int(s[:2])  
    minutes = int(s[2:])  
    return hours * 60 + minutes

def minutes_to_clock(minutes):  
    """Converts minutes since midnight back to HHMM clock format (integer)."""  
    minutes = int(round(minutes))  
    hours = minutes // 60  
    mins = minutes % 60  
    return int(f"{hours:02d}{mins:02d}")

# --- Database Loading ---  
def load_data(db_path="flights_database.db"):  
    """Connects to the database, sets PRAGMAs, creates indexes, and loads all tables."""  
    conn = sqlite3.connect(db_path)  
    conn.execute("PRAGMA journal_mode = MEMORY")  
    conn.execute("PRAGMA synchronous = OFF")  
    conn.execute("PRAGMA temp_store = MEMORY")  
    conn.execute("PRAGMA cache_size = 100000")
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_dest ON flights(dest)")  
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_origin ON flights(origin)")  
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_tailnum ON flights(tailnum)")  
    conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_time_hour ON flights(time_hour)")  
    conn.execute("CREATE INDEX IF NOT EXISTS idx_planes_tailnum ON planes(tailnum)")  
    conn.execute("CREATE INDEX IF NOT EXISTS idx_weather_time_hour ON weather(time_hour)")  
    conn.commit()
    
    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)  
    df_flights  = pd.read_sql_query("SELECT * FROM flights", conn)  
    df_planes   = pd.read_sql_query("SELECT * FROM planes", conn)  
    df_weather  = pd.read_sql_query("SELECT * FROM weather", conn)  
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)
    
    return conn, df_airports, df_flights, df_planes, df_weather, df_airlines

def save_preprocessed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, output_db="preprocessed_flights.db"):  
    """Saves preprocessed DataFrames into a secondary SQLite database."""  
    new_conn = sqlite3.connect(output_db)  
    df_airports.to_sql("airports", new_conn, if_exists="replace", index=False)  
    df_flights.to_sql("flights", new_conn, if_exists="replace", index=False)  
    df_planes.to_sql("planes", new_conn, if_exists="replace", index=False)  
    df_weather.to_sql("weather", new_conn, if_exists="replace", index=False)  
    df_airlines.to_sql("airlines", new_conn, if_exists="replace", index=False)  
    new_conn.commit()  
    new_conn.close()  
    print("Preprocessed data saved to", output_db)

# --- Airport Preprocessing ---  
def augment_airports_with_missing(df_airports, df_flights):  
    """Augments airports table with FAA codes from flights that are missing in the airports table."""  
    flights_dest = set(df_flights['dest'].unique())  
    airports_faa = set(df_airports['faa'].unique())  
    missing_codes = flights_dest - airports_faa

    if not missing_codes:  
        print("No missing airports found.")  
        return df_airports

    print("Missing airports detected:", missing_codes)  
    try:  
        from airportsdata import load  
        airports_dict = load('IATA')  
    except ImportError:  
        print("airportsdata module not available. Install it with 'pip install airportsdata'")  
        return df_airports

    new_rows = []  
    for code in missing_codes:  
        if code in airports_dict:  
            info = airports_dict[code]  
            new_row = {  
                'faa': code,  
                'name': info.get('name', ''),  
                'lat': info.get('lat', None),  
                'lon': info.get('lon', None),  
                'alt': info.get('elevation', None),  
                'tz': np.nan,  
                'dst': np.nan,  
                'tzone': np.nan  
            }  
            new_rows.append(new_row)  
        else:  
            print(f"No external data found for missing airport code: {code}")  
    if new_rows:  
        df_new = pd.DataFrame(new_rows)  
        df_airports = pd.concat([df_airports, df_new], ignore_index=True)  
        print("Augmented airports table with missing data for codes:", sorted(missing_codes))  
    return df_airports

def compute_timezone_info_for_missing(df_airports):  
    """Computes timezone info (tz, dst, tzone) for airports missing this data."""  
    for col in ['tz', 'dst', 'tzone']:  
        if col not in df_airports.columns:  
            df_airports[col] = None

    def compute_info_for_row(row):  
        tz = tf.timezone_at(lng=row['lon'], lat=row['lat'])  
        if tz:  
            try:  
                tz_obj = pytz.timezone(tz)  
                now = pd.Timestamp.now(tz=pytz.utc)  
                local_now = now.astimezone(tz_obj)  
                tz_offset = local_now.utcoffset().total_seconds() / 3600  
                dst_active = "A" if local_now.dst() != pd.Timedelta(0) else "N"  
            except Exception:  
                tz_offset, dst_active = None, None  
        else:  
            tz = None  
            tz_offset, dst_active = None, None  
        return pd.Series([tz_offset, dst_active, tz], index=['tz', 'dst', 'tzone'])

    missing_mask = df_airports[['tz', 'dst', 'tzone']].isna().any(axis=1)  
    df_airports.loc[missing_mask, ['tz', 'dst', 'tzone']] = df_airports.loc[missing_mask].apply(compute_info_for_row, axis=1)  
    return df_airports

def country_to_continent(country_code):  
    """Converts a 2-letter country code to a continent name."""  
    try:  
        continent_code = pc.country_alpha2_to_continent_code(country_code)  
        mapping = {"AF": "Africa", "AS": "Asia", "EU": "Europe",  
                   "NA": "North America", "OC": "Oceania",  
                   "SA": "South America", "AN": "Antarctica"}  
        return mapping.get(continent_code, "Unknown")  
    except Exception:  
        return "Unknown"

def add_location_info_to_airports(df_airports):  
    """Adds reverse geocoded location info (continent, country, city) to airports."""  
    coords = list(zip(df_airports['lat'], df_airports['lon']))  
    results = rg.search(coords, mode=2)  
    continents, countries, cities = [], [], []  
    for res in results:  
        city = res.get('name', 'Unknown')  
        country_code = res.get('cc', 'Unknown')  
        continent = country_to_continent(country_code)  
        try:  
            country_obj = pycountry.countries.get(alpha_2=country_code)  
            country_name = country_obj.name if country_obj else country_code  
        except Exception:  
            country_name = country_code  
        continents.append(continent)  
        countries.append(country_name)  
        cities.append(city)  
    df_airports['continent'] = continents  
    df_airports['country'] = countries  
    df_airports['city'] = cities  
    return df_airports

def compute_airports_distances(df_airports):  
    """Computes distances and bearing from JFK for each airport."""  
    jfk = df_airports[df_airports['faa'] == "JFK"].iloc[0]  
    jfk_lat = radians(jfk['lat'])  
    lat_radians = np.radians(df_airports['lat'].values)  
    lon_radians = np.radians(df_airports['lon'].values)

    df_airports['euclidean_distance'] = np.sqrt((jfk['lat'] - df_airports['lat'])**2 +  
                                                 (jfk['lon'] - df_airports['lon'])**2)  
    R = 6371  
    dlat = lat_radians - jfk_lat  
    dlon = lon_radians - radians(jfk['lon'])  
    a = np.sin(dlat/2)**2 + np.cos(jfk_lat) * np.cos(lat_radians) * np.sin(dlon/2)**2  
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))  
    df_airports['geodesic_distance'] = R * c  
    flight_speed = 900  
    df_airports['estimated_flight_time'] = df_airports['geodesic_distance'] / flight_speed

    # Bearing computation  
    x = np.sin(dlon) * np.cos(lat_radians)  
    y = np.cos(jfk_lat) * np.sin(lat_radians) - np.sin(jfk_lat) * np.cos(lat_radians) * np.cos(dlon)  
    initial_bearing = np.degrees(np.arctan2(x, y))  
    df_airports['bearing'] = (initial_bearing + 360) % 360  
    return df_airports

def preprocess_airports(df_airports, df_flights):  
    """Orchestrates preprocessing for the airports table."""  
    df_airports = augment_airports_with_missing(df_airports, df_flights)  
    df_airports = compute_timezone_info_for_missing(df_airports)  
    df_airports = add_location_info_to_airports(df_airports)  
    df_airports = compute_airports_distances(df_airports)  
    return df_airports

# --- Flight Preprocessing ---  
def fill_dep_time(df):  
    """Fills missing departure times using scheduled departure and delay."""  
    mask = df['dep_time'].isna()  
    df.loc[mask, 'dep_delay'] = df.loc[mask, 'dep_delay'].fillna(0)  
    df.loc[mask, 'dep_time'] = df.loc[mask].apply(  
        lambda row: minutes_to_clock(clock_to_minutes(row['sched_dep_time']) + row['dep_delay']),  
        axis=1  
    )  
    return df

def fill_arr_time(df):  
    """Fills missing arrival times using scheduled arrival and delay."""  
    df['arr_delay'] = df['arr_delay'].fillna(0)  
    mask = df['arr_time'].isna()  
    df.loc[mask, 'arr_time'] = df.loc[mask].apply(  
        lambda row: minutes_to_clock(clock_to_minutes(row['sched_arr_time']) + row['arr_delay']),  
        axis=1  
    )  
    return df

def fill_air_time(df):  
    """Computes air_time for rows missing that value."""  
    mask = df['air_time'].isna()  
    df.loc[mask, 'air_time'] = df.loc[mask].apply(  
        lambda row: clock_to_minutes(row['arr_time']) - clock_to_minutes(row['dep_time']),  
        axis=1  
    )  
    return df

def preprocess_flights(df_flights):  
    """Preprocesses the flights table: deduplication, time conversion, and filling missing times."""  
    df_flights.drop_duplicates(inplace=True)  
    if 'time_hour' in df_flights.columns:  
        df_flights['time_hour'] = df_flights['time_hour'].apply(convert_time_hour_to_utc)  
    df_flights = fill_dep_time(df_flights)  
    df_flights = fill_arr_time(df_flights)  
    df_flights = fill_air_time(df_flights)  
    return df_flights

def compute_local_arrival(df, df_airports):  
    """Computes local arrival time using timezone offsets from the airports table."""  
    tz_mapping = df_airports.set_index('faa')['tz'].to_dict()  
    df['origin_offset'] = df['origin'].map(tz_mapping).fillna(0)  
    df['dest_offset'] = df['dest'].map(tz_mapping).fillna(0)  
    df['tz_diff'] = df['dest_offset'] - df['origin_offset']  
    df['arr_minutes'] = df['arr_time'].apply(clock_to_minutes)  
    df['local_arrival_minutes'] = (df['arr_minutes'] + df['tz_diff'] * 60) % 1440  
    df['local_arrival'] = df['local_arrival_minutes'].apply(minutes_to_clock)  
    df.drop(columns=['origin_offset', 'dest_offset', 'tz_diff', 'arr_minutes', 'local_arrival_minutes'], inplace=True)  
    return df

# --- Plane Preprocessing ---  
def preprocess_planes(df_planes):  
    """Preprocesses the planes table by converting year and filling missing values."""  
    df_planes['year'] = pd.to_numeric(df_planes['year'], errors='coerce')  
    def fill_missing_with_mode(series):  
        non_null = series.dropna()  
        if non_null.empty:  
            return series  
        mode_val = non_null.mode().iloc[0]  
        return series.fillna(mode_val)  
    df_planes['year'] = df_planes.groupby('model')['year'].transform(fill_missing_with_mode)  
    return df_planes

def update_planes_speed(conn):  
    """Updates the speed field in the planes table based on flight data."""  
    df_speed = pd.read_sql_query("""  
        SELECT tailnum, AVG(60.0 * distance / air_time) AS avg_speed  
        FROM flights  
        WHERE air_time > 0  
        GROUP BY tailnum;  
    """, conn)  
    cursor = conn.cursor()  
    update_data = [(row['avg_speed'], row['tailnum']) for _, row in df_speed.iterrows()]  
    cursor.executemany(  
        "UPDATE planes SET speed = ? WHERE tailnum = ? AND (speed IS NULL OR speed = '')",  
        update_data  
    )  
    conn.commit()

# --- Weather Preprocessing ---  
def merge_airport_data(df_weather, df_airports):  
    """Merges airport info into the weather table."""  
    df_airports_subset = df_airports[['faa', 'lat', 'lon', 'tz']]  
    return df_weather.merge(df_airports_subset, left_on='origin', right_on='faa', how='left', suffixes=('', '_airport'))

def convert_time_columns(df_weather):  
    """Converts the time_hour column in weather to a UTC datetime column."""  
    df_weather['dt'] = df_weather['time_hour'].apply(convert_time_hour_to_utc)  
    return df_weather

def get_weather_data_with_backoff(params, max_retries=5):  
    """Makes an API request for weather data with exponential backoff."""  
    for attempt in range(max_retries):  
        try:  
            response = requests.get(BASE_URL, params=params, timeout=10)  
        except Exception as e:  
            print(f"Request exception: {e}")  
            time.sleep(2 ** attempt)  
            continue  
        if response.status_code == 200:  
            return response.json()  
        elif response.status_code == 429:  
            retry_after = response.headers.get("Retry-After")  
            wait = float(retry_after) if retry_after else 2 ** attempt  
            print(f"429 received. Retrying after {wait} seconds...")  
            time.sleep(wait)  
        else:  
            print(f"API request failed with status code {response.status_code}")  
            time.sleep(2 ** attempt)  
    return None

def process_origin_weather(origin, df_weather, df_airports):  
    """For a given origin, updates missing weather data using the API."""  
    try:  
        airport_info = df_airports[df_airports['faa'] == origin].iloc[0]  
    except IndexError:  
        print(f"Origin {origin} not found in airports data.")  
        return pd.DataFrame()
    
    tz = airport_info.get('tz') or 0  
    tzone = airport_info.get('tzone')  
    lat = airport_info['lat']  
    lon = airport_info['lon']
    
    subset = df_weather[df_weather['origin'] == origin].copy()  
    if subset.empty:  
        return subset
    
    subset['local_dt'] = subset['dt'] + pd.to_timedelta(tz, unit='h')  
    start_date = subset['local_dt'].min().strftime("%Y-%m-%d")  
    end_date   = subset['local_dt'].max().strftime("%Y-%m-%d")
    
    params = {  
        "latitude": lat,  
        "longitude": lon,  
        "start_date": start_date,  
        "end_date": end_date,  
        "hourly": HOURLY_PARAMS,  
        "timezone": tzone  
    }
    
    data = get_weather_data_with_backoff(params)  
    if not data:  
        print(f"API request failed for origin {origin}")  
        return subset
    
    hourly_data = data.get("hourly", {})  
    times = hourly_data.get("time", [])  
    field_mapping = {  
        "temperature_2m": "temp",  
        "dewpoint_2m": "dewp",  
        "relativehumidity_2m": "humid",  
        "winddirection_10m": "wind_dir",  
        "windspeed_10m": "wind_speed",  
        "windgusts_10m": "wind_gust",  
        "precipitation": "precip",  
        "surface_pressure": "pressure",  
        "visibility": "visib"  
    }
    
    for idx, row in subset.iterrows():  
        target_time = row['local_dt'].strftime("%Y-%m-%dT%H:00")  
        if target_time in times:  
            idx_in_hourly = times.index(target_time)  
            for api_field, df_field in field_mapping.items():  
                value = hourly_data.get(api_field, [None])[idx_in_hourly]  
                if df_field == "visib" and value is not None:  
                    value = value / 1000.0  
                subset.at[idx, df_field] = value  
        else:  
            print(f"Target time {target_time} not found for origin {origin}")  
    return subset

def preprocess_weather(df_weather, df_airports):  
    """Preprocesses the weather data by merging, converting times, and updating missing info."""  
    df_weather = merge_airport_data(df_weather, df_airports)  
    df_weather = convert_time_columns(df_weather)
    
    missing_mask = df_weather['temp'].isnull()  
    missing_df = df_weather[missing_mask].copy()  
    unique_origins = missing_df['origin'].unique()
    
    if len(unique_origins) <= 4:  
        updated_subsets = []  
        from concurrent.futures import ThreadPoolExecutor  
        with ThreadPoolExecutor(max_workers=len(unique_origins)) as executor:  
            futures = {executor.submit(process_origin_weather, origin, df_weather, df_airports): origin   
                       for origin in unique_origins}  
            for future in concurrent.futures.as_completed(futures):  
                try:  
                    updated_subsets.append(future.result())  
                except Exception as e:  
                    print(f"Error processing origin {futures[future]}: {e}")  
        for subset in updated_subsets:  
            if not subset.empty:  
                df_weather.loc[subset.index, :] = subset  
    else:  
        chunks = np.array_split(missing_df, 4)  
        updated_chunks = []  
        from concurrent.futures import ThreadPoolExecutor  
        with ThreadPoolExecutor(max_workers=4) as executor:  
            futures = {executor.submit(process_origin_weather, chunk['origin'].iloc[0], df_weather, df_airports): i   
                       for i, chunk in enumerate(chunks)}  
            for future in concurrent.futures.as_completed(futures):  
                try:  
                    updated_chunks.append(future.result())  
                except Exception as e:  
                    print(f"Error processing chunk: {e}")  
        for chunk in updated_chunks:  
            if not chunk.empty:  
                df_weather.loc[chunk.index, :] = chunk
    
    df_weather.drop(columns=['faa'], inplace=True, errors='ignore')  
    return df_weather

# --- Airlines Preprocessing ---  
def preprocess_airlines(df_airlines):  
    """Fills missing airline names with 'Unknown'."""  
    if 'name' in df_airlines.columns:  
        missing_count = df_airlines['name'].isnull().sum()  
        if missing_count > 0:  
            print(f"Filling {missing_count} missing values in 'name' with 'Unknown'.")  
            df_airlines['name'] = df_airlines['name'].fillna("Unknown")  
    else:  
        print("The 'name' column is not present in airlines data.")  
    return df_airlines

# --- Preprocessing Orchestration ---  
def print_missing_values(tables):  
    """Prints missing values for each DataFrame in the provided dictionary."""  
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
    """Orchestrates the entire preprocessing pipeline."""  
    df_airlines = preprocess_airlines(df_airlines)  
    print("Missing values in airlines data:\n", df_airlines.isnull().sum())
    
    df_airports = preprocess_airports(df_airports, df_flights)  
    print("Missing values in airports data:\n", df_airports.isnull().sum())
    
    df_flights = preprocess_flights(df_flights)  
    print("Missing values in flights data:\n", df_flights.isnull().sum())
    
    df_planes = preprocess_planes(df_planes)  
    print("Missing values in planes data:\n", df_planes.isnull().sum())
    
    df_weather = preprocess_weather(df_weather, df_airports)  
    print("Missing values in weather data:\n", df_weather.isnull().sum())
    
    update_planes_speed(conn)  
    df_flights = compute_local_arrival(df_flights, df_airports)
    
    tables = {  
        "airports": df_airports,  
        "flights": df_flights,  
        "planes": df_planes,  
        "weather": df_weather,  
        "airlines": df_airlines  
    }  
    print_missing_values(tables)  
    return df_airports, df_flights, df_planes, df_weather, df_airlines

# ============================================================================  
# Part 2: Visualizations  
# ============================================================================  
def create_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, conn):  
    # World map of airports  
    fig_world = px.scatter_geo(  
        df_airports, lat='lat', lon='lon', hover_name='name',  
        title="Airport Locations Worldwide"  
    )  
    fig_world.update_traces(customdata=df_airports['faa'])  
    fig_world.update_layout(clickmode='event+select')
    
    # US airports map  
    df_us_airports = df_airports[df_airports['tzone'].astype(str).str.contains("America", na=False)]  
    fig_us = px.scatter_geo(  
        df_us_airports, lat='lat', lon='lon', hover_name='name',  
        title="US Airports", scope='usa'  
    )
    
    # Altitude colored map  
    fig_alt = px.scatter_geo(  
        df_airports, lat='lat', lon='lon', hover_name='name', color='alt',  
        title="Airports by Altitude", color_continuous_scale="viridis"  
    )
    
    # Distance visualizations  
    fig_geo_dist = px.scatter_geo(  
        df_airports, lat='lat', lon='lon', color='geodesic_distance',  
        hover_name='name', color_continuous_scale='Viridis',  
        title="Geodesic Distance from JFK"  
    )  
    fig_geo_dist.update_geos(showcoastlines=True, coastlinecolor="Black")
    
    fig_euclidean = px.scatter_geo(  
        df_airports, lat='lat', lon='lon', color='euclidean_distance',  
        hover_name='name', color_continuous_scale='Viridis',  
        title="Euclidean Distance from JFK"  
    )  
    fig_euclidean.update_geos(showcoastlines=True, coastlinecolor="Black")
    
    fig_hist_euc = px.histogram(  
        df_airports, x='euclidean_distance',  
        nbins=50, title="Euclidean Distance Distribution"  
    )  
    fig_hist_geo = px.histogram(  
        df_airports, x='geodesic_distance',  
        nbins=50, title="Geodesic Distance Distribution"  
    )  
    fig_hist_time = px.histogram(  
        df_airports, x='estimated_flight_time',  
        nbins=50, title="Estimated Flight Time Distribution"  
    )
    
    # Comparison: Computed vs. DB Flight Distances  
    df_flight_distance = pd.read_sql_query("""  
        SELECT dest, AVG(distance) AS avg_flight_distance  
        FROM flights  
        GROUP BY dest;  
    """, conn)  
    df_compare = pd.merge(df_airports, df_flight_distance, left_on="faa", right_on="dest", how="left")  
    fig_compare = px.scatter(  
        df_compare, x='geodesic_distance', y='avg_flight_distance',  
        title="Computed vs. DB Flight Distances", opacity=0.6,  
        labels={'geodesic_distance': "Geodesic Distance (km)",  
                'avg_flight_distance': "Avg Flight Distance (km)"}  
    )
    
    # Weather & Flight Correlation  
    df_sample = pd.read_sql_query("""  
        SELECT rowid, dest, air_time, time_hour  
        FROM flights  
        WHERE air_time IS NOT NULL  
        LIMIT 500;  
    """, conn)  
    df_merged_weather = pd.merge(  
        df_sample, df_weather[['time_hour','wind_speed','wind_dir']],  
        on='time_hour', how='left'  
    )  
    df_merged_weather = pd.merge(  
        df_merged_weather, df_airports[['faa','bearing']],  
        left_on='dest', right_on='faa', how='left'  
    )  
    df_merged_weather['bearing_rad'] = df_merged_weather['bearing'].apply(lambda x: np.radians(x) if pd.notnull(x) else np.nan)  
    df_merged_weather['wind_dir_rad'] = df_merged_weather['wind_dir'].apply(lambda x: np.radians(x) if pd.notnull(x) else np.nan)  
    df_merged_weather['inner_product'] = (  
        df_merged_weather['wind_speed'] *  
        np.cos(df_merged_weather['bearing_rad'] - df_merged_weather['wind_dir_rad'])  
    )  
    fig_inner_product = px.scatter(  
        df_merged_weather, x='inner_product', y='air_time',  
        title="Inner Product vs. Air Time", opacity=0.5,  
        labels={'inner_product': "Inner Product (Flight Dir · Wind Vec)",  
                'air_time': "Air Time (min)"}  
    )  
    corr_val = df_merged_weather['inner_product'].corr(df_merged_weather['air_time'])
    
    # Airline delay bar chart  
    if 'dep_delay' in df_flights.columns and 'carrier' in df_flights.columns:  
        df_airline_delay = pd.merge(df_flights, df_airlines, on='carrier', how='left')  
        group_delay = df_airline_delay.groupby('name')['dep_delay'].mean().reset_index()  
        fig_airline_delay = px.bar(group_delay, x='name', y='dep_delay',   
                                   title="Average Departure Delay per Airline",  
                                   labels={'dep_delay': 'Avg Dep Delay (min)', 'name': 'Airline'})  
    else:  
        fig_airline_delay = go.Figure()
    
    df_delay = df_flights[['distance', 'arr_delay']].dropna()  
    fig_distance_delay = px.scatter(df_delay, x='distance', y='arr_delay',   
                                    title="Flight Distance vs Arrival Delay",  
                                    labels={'distance':'Flight Distance (km)', 'arr_delay':'Arrival Delay (min)'})  
    corr_value_delay = df_delay['distance'].corr(df_delay['arr_delay'])
    
    df_tz = pd.merge(df_flights, df_airports[['faa', 'tz']], left_on='dest', right_on='faa', how='left')  
    df_tz_counts = df_tz.groupby('tz').size().reset_index(name='count')  
    fig_timezone = px.bar(df_tz_counts, x='tz', y='count',   
                          title="Number of Flights by Destination Time Zone",  
                          text='count',  
                          labels={'tz': 'Time Zone', 'count': 'Flight Count'})
    
    visualizations = {  
        "fig_world": fig_world,  
        "fig_us": fig_us,  
        "fig_alt": fig_alt,  
        "fig_geo_dist": fig_geo_dist,  
        "fig_euclidean": fig_euclidean,  
        "fig_hist_euc": fig_hist_euc,  
        "fig_hist_geo": fig_hist_geo,  
        "fig_hist_time": fig_hist_time,  
        "fig_compare": fig_compare,  
        "fig_airline_delay": fig_airline_delay,  
        "fig_distance_delay": fig_distance_delay,  
        "fig_inner_product": fig_inner_product,  
        "fig_timezone": fig_timezone,  
        "corr_val": corr_val,  
        "corr_value_delay": corr_value_delay  
    }
    
    return visualizations

# ============================================================================  
# Part 4: Main Execution  
# ============================================================================  
if __name__ == '__main__':  
    conn, df_airports, df_flights, df_planes, df_weather, df_airlines = load_data()
    
    preprocessed_db = "preprocessed_flights.db"  
    if os.path.exists(preprocessed_db):  
        print("Loading preprocessed data from", preprocessed_db)  
        conn2 = sqlite3.connect(preprocessed_db)  
        df_airports = pd.read_sql_query("SELECT * FROM airports", conn2)  
        df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn2)  
        df_flights  = pd.read_sql_query("SELECT * FROM flights", conn2)  
        df_planes   = pd.read_sql_query("SELECT * FROM planes", conn2)  
        df_weather  = pd.read_sql_query("SELECT * FROM weather", conn2)  
        conn2.close()  
    else:  
        df_airports, df_flights, df_planes, df_weather, df_airlines = preprocess_data(  
            conn, df_airports, df_flights, df_planes, df_weather, df_airlines  
        )  
        save_preprocessed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
    
    # Create visualizations  
    visualizations = create_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, conn)
    
    # Instead of running a dashboard, iterate through the visualizations dictionary and show the figures  
    for key, fig in visualizations.items():  
        if hasattr(fig, "show"):  
            print(f"Showing visualization: {key}")  
            fig.show()  
        else:  
            print(f"{key}: {fig}")
