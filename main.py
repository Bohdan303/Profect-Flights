import random
import pandas as pd
import numpy as np
import sqlite3
import math
from math import radians, sin, cos, sqrt, atan2
from sklearn.cluster import KMeans
import pytz
from timezonefinder import TimezoneFinder
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

# -------------------------------
# Data Loading Function
# -------------------------------
def load_data(csv_path="airports.csv"):
    """
    Load and preprocess the airports data.
    
    - Reads the CSV file.
    - Renames columns.
    - Fills in missing timezone data using TimezoneFinder.
    - Drops any rows with missing values.
    
    Parameters:
        csv_path (str): Path to the airports CSV file.
        
    Returns:
        pd.DataFrame: Preprocessed DataFrame.
    """
    df = pd.read_csv(csv_path, delimiter=",")
    df.columns = ["FAA", "name", "lat", "lon", "alt", "tz", "dst", "tzone"]
    
    tf = TimezoneFinder()
    
    def get_timezone_data(row):
        try:
            if pd.isna(row['tz']) or pd.isna(row['dst']) or pd.isna(row['tzone']):
                timezone = tf.timezone_at(lng=row['lon'], lat=row['lat'])
                if timezone:
                    tz_obj = pytz.timezone(timezone)
                    now = pd.Timestamp.now(tz=pytz.utc)
                    local_now = now.astimezone(tz_obj)
                    tz_offset = local_now.utcoffset().total_seconds() / 3600  # seconds to hours
                    dst_active = "A" if local_now.dst() != pd.Timedelta(0) else "N"
                    return pd.Series([tz_offset, dst_active, timezone], index=['tz', 'dst', 'tzone'])
        except Exception as e:
            pass
        
        return pd.Series([row['tz'], row['dst'], row['tzone']], index=['tz', 'dst', 'tzone'])
    
    df[['tz', 'dst', 'tzone']] = df.apply(get_timezone_data, axis=1)
    df = df.dropna()
    return df

# -------------------------------
# Calculations
# -------------------------------
R = 6371  # Earth's radius in km

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Haversine (geodesic) distance between two points on the Earth.
    
    Parameters:
        lat1, lon1: Latitude and longitude of the first point.
        lat2, lon2: Latitude and longitude of the second point.
        
    Returns:
        float: Distance in kilometers.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def euclidean_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Euclidean distance (as a rough approximation) between two points.
    
    Parameters:
        lat1, lon1: Latitude and longitude of the first point.
        lat2, lon2: Latitude and longitude of the second point.
        
    Returns:
        float: Euclidean distance.
    """
    return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def calculate_all(df):
    """
    Calculate all required metrics and add them as new columns to the DataFrame:
      - Euclidean distance from JFK
      - Geodesic distance from JFK
      - Estimated flight time (based on average speed)
      - Cluster assignment using KMeans
    
    Parameters:
        df (pd.DataFrame): DataFrame containing airports data.
        
    Returns:
        pd.DataFrame: Updated DataFrame with new columns.
    """
    # Get JFK's data
    jfk = df[df['FAA'] == "JFK"].iloc[0]
    jfk_lat = jfk['lat']
    jfk_lon = jfk['lon']
    
    # Euclidean distance
    df['euclidean_distance'] = df.apply(
        lambda row: euclidean_distance(jfk_lat, jfk_lon, row['lat'], row['lon']),
        axis=1
    )
    
    # Geodesic (Haversine) distance
    df['geodesic_distance'] = df.apply(
        lambda row: haversine_distance(jfk_lat, jfk_lon, row['lat'], row['lon']),
        axis=1
    )
    
    # KMeans clustering (using lat, lon)
    coordinates = df[['lat', 'lon']]
    kmeans = KMeans(n_clusters=10, random_state=42)
    df['cluster'] = kmeans.fit_predict(coordinates)
    
    # Estimated flight time in hours (using an average flight speed of 900 km/h)
    flight_speed = 900
    df['estimated_flight_time'] = df['geodesic_distance'] / flight_speed
    
    return df

# -------------------------------
# Database Queries
# -------------------------------
DB_PATH = 'flights_database.db'
NYC_COORD = (40.6413, -73.7781)  # Approximate JFK coordinates

def verify_distance_calculation():
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT origin, dest, distance FROM flights LIMIT 10;"
        df = pd.read_sql(query, conn)
    print("Sample distances from flights table:")
    print(df)

def identify_nyc_departure_airports():
    with sqlite3.connect(DB_PATH) as conn:
        query = """
        SELECT a.*
        FROM airports a
        WHERE a.faa IN (
            SELECT DISTINCT origin FROM flights
        );
        """
        df = pd.read_sql(query, conn)
    print("NYC Departure Airports:")
    print(df)
    return df

def flight_destinations_on_day(month, day, airport):
    with sqlite3.connect(DB_PATH) as conn:
        month_str = f"{month:02d}"
        day_str = f"{day:02d}"
        query = f"""
        SELECT f.dest, a.lat AS latitude, a.lon AS longitude, a.name
        FROM flights f
        JOIN airports a ON f.dest = a.faa
        WHERE f.origin = '{airport}'
          AND strftime('%m', f.month) = '{month_str}'
          AND strftime('%d', f.day) = '{day_str}';
        """
        df = pd.read_sql(query, conn)
    if df.empty:
        print(f"No flights found for {airport} on {month_str}-{day_str}.")
    else:
        print(f"Flight destinations for {airport} on {month_str}-{day_str}:")
        print(df)
        fig = px.scatter_geo(df, lat='latitude', lon='longitude', hover_name='name',
                             title=f"Destinations from {airport} on {month_str}-{day_str}")
        fig.show()
    return df

def flight_statistics_for_day(month, day, airport):
    with sqlite3.connect(DB_PATH) as conn:
        month_str = f"{month:02d}"
        day_str = f"{day:02d}"
        query = f"""
        SELECT f.dest, a.lat AS latitude, a.lon AS longitude, a.name
        FROM flights f
        JOIN airports a ON f.dest = a.faa
        WHERE f.origin = '{airport}'
          AND strftime('%m', f.month) = '{month_str}'
          AND strftime('%d', f.day) = '{day_str}';
        """
        df = pd.read_sql(query, conn)
    if df.empty:
        print(f"No flights found for {airport} on {month_str}-{day_str}.")
    else:
        print(f"Flight destinations for {airport} on {month_str}-{day_str}:")
        print(df)
        fig = px.scatter_geo(df, lat='latitude', lon='longitude', hover_name='name',
                             title=f"Destinations from {airport} on {month_str}-{day_str}")
        fig.show()
    return df

def plane_types_on_route(departure, arrival):
    with sqlite3.connect(DB_PATH) as conn:
        query_tailnum = f"""
        SELECT tailnum, COUNT(*) as count
        FROM flights
        WHERE origin = '{departure}' AND dest = '{arrival}'
        GROUP BY tailnum;
        """
        tailnum_df = pd.read_sql(query_tailnum, conn)
        
        result = {}
        for _, row in tailnum_df.iterrows():
            tailnum = row['tailnum']
            count = row['count']
            query_type = f"SELECT type FROM planes WHERE tailnum = '{tailnum}' LIMIT 1;"
            type_df = pd.read_sql(query_type, conn)
            if not type_df.empty:
                plane_type = type_df.iloc[0]['type']
                result[plane_type] = result.get(plane_type, 0) + count
    print(f"Plane types on route {departure} to {arrival}:", result)
    return result

def average_dep_delay_per_airline():
    with sqlite3.connect(DB_PATH) as conn:
        query_delay = """
        SELECT carrier, AVG(dep_delay) as avg_dep_delay
        FROM flights
        GROUP BY carrier;
        """
        delay_df = pd.read_sql(query_delay, conn)
        query_airlines = "SELECT carrier AS code, name FROM airlines;"
        airlines_df = pd.read_sql(query_airlines, conn)
    merged_df = pd.merge(delay_df, airlines_df, left_on='carrier', right_on='code', how='left')
    print("Average departure delays per airline:")
    print(merged_df)
    fig = px.bar(merged_df, x='name', y='avg_dep_delay',
                 title="Average Departure Delay per Airline")
    fig.update_layout(xaxis_tickangle=-45)
    fig.show()
    return merged_df

def delayed_flights_for_destination(start_month, end_month, destination):
    with sqlite3.connect(DB_PATH) as conn:
        start_str = f"{start_month:02d}"
        end_str = f"{end_month:02d}"
        query = f"""
        SELECT COUNT(*) as delayed_flights
        FROM flights
        WHERE dest = '{destination}'
          AND strftime('%m', month) BETWEEN '{start_str}' AND '{end_str}'
          AND arr_delay > 0;
        """
        df = pd.read_sql(query, conn)
    delayed = df.iloc[0]['delayed_flights']
    print(f"Delayed flights to {destination} between months {start_str} and {end_str}: {delayed}")
    return delayed

def top_airplane_manufacturers_for_destination(destination):
    with sqlite3.connect(DB_PATH) as conn:
        query = f"""
        SELECT p.manufacturer, COUNT(*) as count
        FROM flights f
        JOIN planes p ON f.tailnum = p.tailnum
        WHERE f.dest = '{destination}'
        GROUP BY p.manufacturer
        ORDER BY count DESC
        LIMIT 5;
        """
        df = pd.read_sql(query, conn)
    print(f"Top 5 airplane manufacturers for destination {destination}:")
    print(df)
    return df

def relationship_distance_arr_delay():
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT distance, arr_delay FROM flights;"
        df = pd.read_sql(query, conn)
    fig = px.scatter(df, x='distance', y='arr_delay', title="Flight Distance vs Arrival Delay")
    fig.show()
    corr = df['distance'].corr(df['arr_delay'])
    print(f"Correlation between flight distance and arrival delay: {corr}")
    return corr

def compute_average_speed_each_plane():
    with sqlite3.connect(DB_PATH) as conn:
        query = """
        SELECT tailnum, AVG(distance*1.0/air_time) as avg_speed
        FROM flights
        WHERE air_time > 0
        GROUP BY tailnum;
        """
        speed_df = pd.read_sql(query, conn)
        cur = conn.cursor()
        for _, row in speed_df.iterrows():
            tailnum = row['tailnum']
            avg_speed = row['avg_speed']
            cur.execute("UPDATE planes SET speed = ? WHERE tailnum = ?", (avg_speed, tailnum))
        conn.commit()
    print("Updated average speeds in the planes table.")
    return speed_df

def compute_flight_directions():
    def calculate_bearing(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dLon = lon2 - lon1
        x = math.sin(dLon) * math.cos(lat2)
        y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dLon)
        initial_bearing = math.atan2(x, y)
        return (math.degrees(initial_bearing) + 360) % 360
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT faa, lat AS latitude, lon AS longitude, name FROM airports;"
        df = pd.read_sql(query, conn)
    df['bearing'] = df.apply(lambda row: calculate_bearing(NYC_COORD[0], NYC_COORD[1],
                                                           row['latitude'], row['longitude']), axis=1)
    print("Flight directions from NYC (first 10 airports):")
    print(df[['faa', 'name', 'bearing']].head(10))
    return df

def inner_product_flight_direction_wind(flight_id):
    with sqlite3.connect(DB_PATH) as conn:
        # Use rowid as the identifier since flights table doesn't have an "id" column
        query_flight = f"SELECT origin, dest, air_time, year, month, day FROM flights WHERE rowid = {flight_id} LIMIT 1;"
        flight_df = pd.read_sql(query_flight, conn)
        if flight_df.empty:
            print(f"Flight with id {flight_id} not found.")
            return None
        flight = flight_df.iloc[0]
        
        query_airport = f"SELECT lat AS latitude, lon AS longitude FROM airports WHERE faa = '{flight['dest']}' LIMIT 1;"
        airport_df = pd.read_sql(query_airport, conn)
        if airport_df.empty:
            print(f"Destination airport {flight['dest']} not found.")
            return None
        dest = airport_df.iloc[0]
        
        def calculate_bearing(lat1, lon1, lat2, lon2):
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            dLon = lon2 - lon1
            x = math.sin(dLon) * math.cos(lat2)
            y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
            initial_bearing = math.atan2(x, y)
            return (math.degrees(initial_bearing) + 360) % 360
        
        # Calculate bearing from NYC to destination
        bearing = calculate_bearing(NYC_COORD[0], NYC_COORD[1], dest['latitude'], dest['longitude'])
        flight_vector = (math.cos(math.radians(bearing)), math.sin(math.radians(bearing)))
        
        # Query weather using flight origin and flight date details
        query_weather = (
            f"SELECT wind_speed, wind_dir FROM weather "
            f"WHERE origin = '{flight['origin']}' "
            f"AND year = {flight['year']} "
            f"AND month = {flight['month']} "
            f"AND day = {flight['day']} LIMIT 1;"
        )
        weather_df = pd.read_sql(query_weather, conn)
        if weather_df.empty:
            print("No weather data found for the flight date and origin.")
            return None
        weather = weather_df.iloc[0]
        
        # Calculate wind vector from wind direction and speed
        wind_vector = (math.cos(math.radians(weather['wind_dir'])), math.sin(math.radians(weather['wind_dir'])))
        wind_vector = (wind_vector[0] * weather['wind_speed'], wind_vector[1] * weather['wind_speed'])
        
        inner_product = flight_vector[0] * wind_vector[0] + flight_vector[1] * wind_vector[1]
        print(f"Inner product for flight {flight_id}: {inner_product}")
        return inner_product

def relationship_wind_direction_air_time():
    results = []
    with sqlite3.connect(DB_PATH) as conn:
        # Use rowid as the flight identifier
        query = "SELECT rowid as id, air_time FROM flights LIMIT 50;"
        flights_df = pd.read_sql(query, conn)
        for _, row in flights_df.iterrows():
            flight_id = row['id']
            inner = inner_product_flight_direction_wind(flight_id)
            if inner is not None:
                results.append({
                    'id': flight_id,
                    'air_time': row['air_time'],
                    'inner_product': inner
                })
    if results:
        results_df = pd.DataFrame(results)
        results_df['inner_sign'] = results_df['inner_product'].apply(lambda x: 'Positive' if x >= 0 else 'Negative')
        print("Relationship between wind direction and air time (sample):")
        print(results_df)
        fig = px.box(results_df, x='inner_sign', y='air_time', title="Air Time vs. Wind Inner Product Sign")
        fig.show()
        return results_df
    else:
        print("No data available for analysis.")
        return None

def run_all_db_functions():
    print("1️⃣ Verifying Distance Calculation:")
    verify_distance_calculation()
    
    print("\n2️⃣ Identifying NYC Departure Airports:")
    identify_nyc_departure_airports()
    
    print("\n3️⃣ Flight Destinations on a Given Day (example: JFK on 01-01):")
    flight_destinations_on_day(1, 1, 'JFK')
    
    print("\n4️⃣ Flight Statistics for a Given Day (example: JFK on 01-01):")
    flight_statistics_for_day(1, 1, 'JFK')
    
    print("\n5️⃣ Plane Types on Route (example: JFK to LAX):")
    plane_types_on_route('JFK', 'LAX')
    
    print("\n6️⃣ Average Departure Delays per Airline:")
    average_dep_delay_per_airline()
    
    print("\n7️⃣ Delayed Flights for Destination (example: LAX, months 1 to 3):")
    delayed_flights_for_destination(1, 3, 'LAX')
    
    print("\n8️⃣ Top 5 Airplane Manufacturers for Destination (example: LAX):")
    top_airplane_manufacturers_for_destination('LAX')
    
    print("\n9️⃣ Relationship Between Distance and Arrival Delay:")
    relationship_distance_arr_delay()
    
    print("\n🔟 Compute Average Speed of Each Plane Model:")
    compute_average_speed_each_plane()
    
    print("\n1️⃣1️⃣ Compute Flight Directions from NYC Airports:")
    compute_flight_directions()
    
    print("\n1️⃣2️⃣ Inner Product of Flight Direction and Wind Speed (example flight id 1):")
    inner_product_flight_direction_wind(1)
    
    print("\n1️⃣3️⃣ Relationship Between Wind Direction and Air Time:")
    relationship_wind_direction_air_time()

# -------------------------------
# Visualizations: Bar Charts / Histograms
# -------------------------------
def plot_timezone_bar_chart(df):
    """
    Plot a bar chart for the distribution of airports by time zone.
    """
    timezone_counts = df['tz'].value_counts()
    plt.figure(figsize=(12, 6))
    sns.barplot(x=timezone_counts.index, y=timezone_counts.values, palette="coolwarm")
    plt.xticks(rotation=45)
    plt.xlabel("Time Zones")
    plt.ylabel("Number of Airports")
    plt.title("Time Zones Distribution of Airports")
    plt.show()

def plot_histogram_euclidean(df):
    """
    Plot a histogram for Euclidean distances from JFK.
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['euclidean_distance'], bins=50, color='blue')
    plt.xlabel("Euclidean Distance from JFK")
    plt.ylabel("Number of Airports")
    plt.title("Distribution of Euclidean Distances from JFK")
    plt.show()

def plot_histogram_geodesic(df):
    """
    Plot a histogram for Geodesic distances from JFK.
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['geodesic_distance'], bins=50, color='orange')
    plt.xlabel("Geodesic Distance from JFK (km)")
    plt.ylabel("Number of Airports")
    plt.title("Distribution of Geodesic Distances from JFK")
    plt.show()

def plot_histogram_flight_time(df):
    """
    Plot a histogram for Estimated Flight Times from JFK.
    """
    plt.figure(figsize=(10, 6))
    plt.hist(df['estimated_flight_time'], bins=50, color='purple', edgecolor='black')
    plt.xlabel('Estimated Flight Time (hours)')
    plt.ylabel('Number of Airports')
    plt.title('Distribution of Estimated Flight Times from JFK')
    plt.show()

# -------------------------------
# Visualizations: Pie Charts
# -------------------------------
def plot_timezone_pie_chart(df):
    """
    Plot a pie chart for the time zones distribution of airports.
    """
    timezone_counts = df['tz'].value_counts()
    
    plt.figure(figsize=(8, 8))
    plt.pie(timezone_counts, labels=timezone_counts.index, autopct='%1.1f%%', 
            colors=sns.color_palette("coolwarm", len(timezone_counts)), startangle=90)
    plt.title("Time Zones Distribution of Airports")
    plt.axis('equal')
    plt.show()
    
    # Pie chart with percentages outside and lines pointing to wedges
    plt.figure(figsize=(10, 8))
    wedges, texts, autotexts = plt.pie(
        timezone_counts, labels=timezone_counts.index, autopct='%1.1f%%', 
        colors=sns.color_palette("coolwarm", len(timezone_counts)), startangle=90,
        wedgeprops={'edgecolor': 'black', 'linewidth': 1.5},
        pctdistance=1.1, labeldistance=100
    )
    
    for text in texts:
        text.set_fontsize(12)
        text.set_fontweight('bold')
    
    for autotext in autotexts:
        autotext.set_fontsize(12)
        autotext.set_fontweight('bold')
    
    plt.legend(wedges, timezone_counts.index, title="Time Zones", loc="upper left", bbox_to_anchor=(1, 1))
    plt.title("Time Zones Distribution of Airports")
    plt.axis('equal')
    plt.show()

# -------------------------------
# Visualizations: Route Plotting
# -------------------------------
def plot_routes(df, airport_codes):
    """
    Plot multiple flight routes from JFK to the given airport codes.
    Routes are color-coded based on geodesic distance.
    
    Parameters:
        df (pd.DataFrame): DataFrame with airports data.
        airport_codes (list): List of FAA codes to plot routes for.
    """
    # Get JFK's location
    jfk_row = df[df['FAA'] == "JFK"]
    if jfk_row.empty:
        print("JFK airport not found.")
        return
    jfk_lat = jfk_row.iloc[0]['lat']
    jfk_lon = jfk_row.iloc[0]['lon']
    
    # Compute global min and max geodesic distances (for normalization)
    min_distance = df['geodesic_distance'].min()
    max_distance = df['geodesic_distance'].max()
    
    fig = go.Figure()
    
    for code in airport_codes:
        target = df[df['FAA'] == code]
        if target.empty:
            print(f"Invalid airport code: {code}")
            continue
        target_lat = target.iloc[0]['lat']
        target_lon = target.iloc[0]['lon']
        distance = haversine_distance(jfk_lat, jfk_lon, target_lat, target_lon)
        norm_value = (distance - min_distance) / (max_distance - min_distance)
        color = sample_colorscale('Viridis', [norm_value])[0]
        
        fig.add_trace(go.Scattergeo(
            lat=[jfk_lat, target_lat],
            lon=[jfk_lon, target_lon],
            mode='lines+markers',
            line=dict(width=2, color=color),
            marker=dict(size=8, symbol="circle"),
            text=f"{code} ({distance:.2f} km)", 
            name=f"JFK → {code} ({distance:.2f} km)"
        ))
    
    fig.update_layout(
        title="Flight Routes from JFK",
        geo=dict(showland=True, landcolor="lightgray")
    )
    fig.show()

# -------------------------------
# Visualizations: Scatter Plots
# -------------------------------
def plot_world_airports(df):
    """
    Plot world airports using a scatter_geo map.
    """
    fig = px.scatter_geo(df, lat='lat', lon='lon', hover_name='name', 
                          title="Airport Locations Worldwide")
    fig.show()

def plot_us_airports(df_us):
    """
    Plot US airports using a scatter_geo map.
    """
    fig = px.scatter_geo(df_us, lat='lat', lon='lon', hover_name='name', 
                          title="US Airports")
    fig.show()

def plot_altitude_scatter(df):
    """
    Scatter plot: Estimated Flight Time vs Airport Altitude.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(df['alt'], df['estimated_flight_time'], color='green', alpha=0.5)
    plt.xlabel('Airport Altitude (m)')
    plt.ylabel('Estimated Flight Time (hours)')
    plt.title('Estimated Flight Time vs Airport Altitude')
    plt.show()

def plot_geodesic_vs_altitude(df):
    """
    Scatter plot: Geodesic Distance from JFK vs Airport Altitude.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(df['geodesic_distance'], df['alt'], color='red', alpha=0.5)
    plt.xlabel('Geodesic Distance from JFK (km)')
    plt.ylabel('Airport Altitude (m)')
    plt.title('Geodesic Distance vs Airport Altitude')
    plt.show()

def plot_distance_heatmaps(df):
    """
    Create scatter_geo heatmaps for geodesic and Euclidean distances from JFK.
    """
    fig_geo = px.scatter_geo(df, lat='lat', lon='lon', 
                             color='geodesic_distance', hover_name='name',
                             color_continuous_scale='Viridis',
                             title="Airports Heatmap by Geodesic Distance from JFK")
    fig_geo.update_geos(showcoastlines=True, coastlinecolor="Black")
    fig_geo.show()
    
    fig_euclid = px.scatter_geo(df, lat='lat', lon='lon', 
                                color='euclidean_distance', hover_name='name',
                                color_continuous_scale='Viridis',
                                title="Airports Heatmap by Euclidean Distance from JFK")
    fig_euclid.update_geos(showcoastlines=True, coastlinecolor="Black")
    fig_euclid.show()

def plot_timezone_map(df):
    """
    Plot a scatter_geo map with airports colored by their time zone.
    """
    fig = px.scatter_geo(df, lat='lat', lon='lon', hover_name='name', 
                         color='tz', title="Airports by Time Zone",
                         color_continuous_scale="viridis")
    fig.show()

# -------------------------------
# Main Function
# -------------------------------
def main():
    # --- Data Loading ---
    print("Loading data...")
    df = load_data("airports.csv")
    
    # --- Calculations ---
    print("Calculating distances, flight times, and clusters...")
    df = calculate_all(df)
    
    # Optional: Filter US airports if needed for some plots
    df_us_airports = df[df['tzone'].str.contains("America", na=False)]
    
    # --- Visualizations ---
    
    # Scatter Plots
    print("Generating scatter plots...")
    plot_world_airports(df)
    plot_us_airports(df_us_airports)
    plot_altitude_scatter(df)
    plot_geodesic_vs_altitude(df)
    plot_distance_heatmaps(df)
    plot_timezone_map(df)
    
    # Route Plotting
    print("Plotting flight routes from JFK...")
    user_input = input("Enter FAA codes separated by commas with no spaces (FAA,FAA,FAA):")
    input_FAA_codes = [code.strip().upper() for code in user_input.split(",") if code.strip()]
    plot_routes(df, input_FAA_codes)
    
    # Bar Charts / Histograms
    print("Generating bar charts and histograms...")
    plot_timezone_bar_chart(df)
    plot_histogram_euclidean(df)
    plot_histogram_geodesic(df)
    plot_histogram_flight_time(df)
    
    # Pie Charts
    print("Generating pie charts...")
    plot_timezone_pie_chart(df)
    
    # Database Queries
    print("Running database queries...")
    run_all_db_functions()
    
if __name__ == "__main__":
    main()