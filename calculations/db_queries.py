import sqlite3
import pandas as pd
import math
import plotly.express as px
import plotly.graph_objects as go
from calculations.calculations import haversine_distance

DB_PATH = 'flights_database.db'


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

def run_all_db_functions():
    # print("1️⃣ Verifying Distance Calculation:")
    # verify_distance_calculation()
    
    # print("\n2️⃣ Identifying NYC Departure Airports:")
    # identify_nyc_departure_airports()
    
    # print("\n3️⃣ Flight Destinations on a Given Day (example: JFK on 01-01):")
    # flight_destinations_on_day(1, 1, 'JFK')
    
    # print("\n4️⃣ Flight Statistics for a Given Day (example: JFK on 01-01):")
    # flight_statistics_for_day(1, 1, 'JFK')
    
    # print("\n5️⃣ Plane Types on Route (example: JFK to LAX):")
    # plane_types_on_route('JFK', 'LAX')
    
    # print("\n6️⃣ Average Departure Delays per Airline:")
    # average_dep_delay_per_airline()
    
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