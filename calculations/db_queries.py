import sqlite3
import pandas as pd
import math
import plotly.express as px
import plotly.graph_objects as go


DB_PATH = 'flights_db_extracted/flights_database.db'

#Point 1
def verify_distances():
    """
    Verify computed distances with flight distances from the flights table.
    """
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT origin, dest, distance FROM flights LIMIT 10"
        df = pd.read_sql(query, conn)
        print('Sample flight distances from database:')
        print(df)

#Point 2
def get_nyc_airports():
    """
    Identify different NYC departure airports using the flights table.
    Returns a DataFrame with airport details.
    """
    with sqlite3.connect(DB_PATH) as conn:
        query = """
        SELECT * FROM airports
        WHERE faa IN (SELECT DISTINCT origin FROM flights)
        """
        df = pd.read_sql(query, conn)
        return df

#Point 3
def plot_flight_destinations(month, day, airport):
    """
    Plot all flight destinations from a specific NYC airport on a given day.
    Assumes the flights table has a 'date' column in 'YYYY-MM-DD' format.
    """
    with sqlite3.connect(DB_PATH) as conn:
        month_str = f'{month:02d}'
        day_str = f'{day:02d}'
        query = f"""
        SELECT f.dest, a.latitude, a.longitude, a.name 
        FROM flights f
        JOIN airports a ON f.dest = a.faa
        WHERE f.origin = '{airport}'
        AND strftime('%m', f.date) = '{month_str}'
        AND strftime('%d', f.date) = '{day_str}'
        """
        df = pd.read_sql(query, conn)
        if df.empty:
            print(f'No flights found for {airport} on {month_str}-{day_str}')
        else:
            title = f'Flight Destinations from {airport} on {month_str}-{day_str}'
            plot_airports_world(df, title=title)

#Point 4
def flight_statistics_for_day(month, day, airport):
    with sqlite3.connect(DB_PATH) as conn:
        query_stats = f"""
        SELECT COUNT(*) as total_flights, COUNT(DISTINCT dest) as unique_destinations
        FROM flights
        WHERE origin = '{airport}'
        AND month = {month}
        AND day = {day}
        """
        stats_df = pd.read_sql(query_stats, conn)
        
        query_most = f"""
        SELECT dest, COUNT(*) as flight_count
        FROM flights
        WHERE origin = '{airport}'
        AND month = {month}
        AND day = {day}
        GROUP BY dest
        ORDER BY flight_count DESC
        LIMIT 1
        """
        most_df = pd.read_sql(query_most, conn)
        
        result = stats_df.to_dict('records')[0]
        result['most_visited'] = most_df.iloc[0]['dest'] if not most_df.empty else None
        print(result)
        return result
    
#point 5
def plane_types_on_route(departure, arrival):
    with sqlite3.connect(DB_PATH) as conn:
        query = f"""
        SELECT tailnum, COUNT(*) as count
        FROM flights
        WHERE origin = '{departure}' AND dest = '{arrival}'
        GROUP BY tailnum
        """
        tailnum_df = pd.read_sql(query, conn)
        if tailnum_df.empty:
            print(f'No flights found from {departure} to {arrival}')
            return {}
        
        result = {}
        for _, row in tailnum_df.iterrows():
            tailnum = row['tailnum']
            count = row['count']
            query_type = f"SELECT type FROM planes WHERE tailnum = '{tailnum}'"
            type_df = pd.read_sql(query_type, conn)
            if not type_df.empty:
                plane_type = type_df.iloc[0]['type']
                result[plane_type] = result.get(plane_type, 0) + count
        print(result)
        return result

#point 6
def average_dep_delay_per_airline():
    """
    Compute and visualize the average departure delay per airline.
    Joins the flights table with the airlines table to use full airline names.
    """
    with sqlite3.connect(DB_PATH) as conn:
        query = """
        SELECT carrier, AVG(dep_delay) as avg_dep_delay
        FROM flights
        GROUP BY carrier
        """
        delay_df = pd.read_sql(query, conn)
        
        # Join with airlines table to get full airline names
        query_airlines = "SELECT carrier as iata, name FROM airlines"
        airlines_df = pd.read_sql(query_airlines, conn)
        merged = pd.merge(delay_df, airlines_df, left_on='carrier', right_on='iata', how='left')
        
        print(f"See graph for average departure delay per airline.")
        fig = px.bar(merged, x='name', y='avg_dep_delay',
            title='Average Departure Delay per Airline')
        fig.update_layout(xaxis_tickangle=-45)
        fig.show()
        
        return merged

#point 7
def delayed_flights_for_destination(start_month, end_month, destination):
    with sqlite3.connect(DB_PATH) as conn:
        start_str = f"{start_month:02d}"
        end_str = f"{end_month:02d}"
        query = f"""
        SELECT COUNT(*) as delayed_flights
        FROM flights
        WHERE dest = '{destination}'
        AND strftime('%m', date) BETWEEN '{start_str}' AND '{end_str}'
        AND arr_delay > 0;
        """
        df = pd.read_sql(query, conn)
    delayed = df.iloc[0]['delayed_flights']
    print(f"Delayed flights to {destination} between months {start_str} and {end_str}: {delayed}")
    return delayed

#point 8
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

#point 9
def relationship_distance_arr_delay():
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT distance, arr_delay FROM flights;"
        df = pd.read_sql(query, conn)
    fig = px.scatter(df, x='distance', y='arr_delay', title="Flight Distance vs Arrival Delay")
    fig.show()
    corr = df['distance'].corr(df['arr_delay'])
    print(f"Correlation between flight distance and arrival delay: {corr}")
    return corr

#point 10
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

def run_all_db_functions():
    # print("1️⃣ Verifying Distance Calculation:")
    # verify_distance_calculation()
    
    # print("\n2️⃣ Identifying NYC Departure Airports:")
    # identify_nyc_departure_airports()
    
    # print("\n3️⃣ Flight Destinations on a Given Day (example: JFK on 01-01):")
    # flight_destinations_on_day(1, 1, 'JFK')
    
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
    
    # print("\n1️⃣1️⃣ Compute Flight Directions from NYC Airports:")
    # compute_flight_directions()
    
    # print("\n1️⃣2️⃣ Inner Product of Flight Direction and Wind Speed (example flight id 1):")
    # inner_product_flight_direction_wind(1)
    
    # print("\n1️⃣3️⃣ Relationship Between Wind Direction and Air Time:")
    # relationship_wind_direction_air_time()