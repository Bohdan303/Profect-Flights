# dashboard/app.py

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from visualizations import index as vis

@st.cache_resource
def load_visualizations():
    conn = sqlite3.connect("processed_flights.db")
    return vis.create_all_visualizations(conn)

def run_dashboard():
    # Open connection to preprocessed database
    conn = sqlite3.connect("processed_flights.db")
    
    #set up page
    st.set_page_config(
        page_title="Flights Dashboard",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    airport_dest_query = "SELECT DISTINCT dest FROM flights"
    df_dest_airports = pd.read_sql_query(airport_dest_query, conn)
    dest_airport_list = sorted(df_dest_airports["dest"].tolist())

    airport_origin_query = "SELECT DISTINCT origin FROM flights"
    df_origin_query = pd.read_sql_query(airport_origin_query, conn)
    origin_airport_list = sorted(df_origin_query["origin"].tolist())

    #create sidebar
    with st.sidebar:
        #create tabs
        tab = st.sidebar.radio(
            "Select Tab",
            options=[
                "General Statistics", 
                "General Maps", 
                "Flight Routes", 
                "Distance Analysis", 
                "Flights by Day", 
                "Trajectory Statistics", 
                "Manufacturer & Airline Statistics", 
                "Plane Delay Analysis"
            ]
        )
        origin_airport = st.selectbox("Select Departure Airport", origin_airport_list)
        dest_airport = st.sidebar.multiselect("Select Arrival Airports (FAA codes)", dest_airport_list)
          
    visuals = load_visualizations()
    
    if tab == "General Statistics":
        st.header("General Statistics")
        # Average departure delay by destination time zone
        query = """
        SELECT tz, AVG(dep_delay_final) as avg_dep_delay
        FROM (
            SELECT f.dep_delay_final, a.tz
            FROM flights f
            JOIN airports a ON f.dest = a.faa
        )
        GROUP BY tz
        """
        df_stats = pd.read_sql_query(query, conn)
        fig_stats = px.bar(df_stats, x="tz", y="avg_dep_delay",
                           title="Avg Departure Delay by Destination Time Zone",
                           labels={"tz": "Time Zone", "avg_dep_delay": "Avg Departure Delay (min)"})
        st.plotly_chart(fig_stats)
        
        query_stats = """
        SELECT 
            DISTINCT flight, COUNT(*) AS num_flights, 
            AVG(dep_delay_final) AS avg_dep_delay,
            (SELECT dest FROM flights GROUP BY dest ORDER BY COUNT(*) DESC LIMIT 1) AS most_popular_dest
        FROM flights
        """
        df_stats = pd.read_sql_query(query_stats, conn)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Flights", df_stats["num_flights"])
        col2.metric("Avg Departure Delay (min)", f"{df_stats['avg_dep_delay'].iloc[0]:.2f}")
        col3.metric("Most Popular Destination", df_stats["most_popular_dest"].iloc[0])    
        
    elif tab == "General Maps":
        st.header("General Maps")
        st.subheader("World Airport Map")
        st.plotly_chart(visuals.get("fig_world"))
        st.subheader("World Airport Map by Altitude")
        st.plotly_chart(visuals.get("fig_alt"))
        st.subheader("US Airport Map")
        st.plotly_chart(visuals.get("fig_us"))
        st.subheader("US Airport Map by Altitude")
        st.plotly_chart(visuals.get("fig_us_alt"))
        
    elif tab == "Flight Routes":
        st.header("Flight Routes")
        st.text("Select a departure airport and multiple arrival airports in the sidebar and press the plot routes button.")
        selected_arrival_airports = dest_airport
    
        if st.button("Plot Routes"):
            fig = px.scatter_geo(scope="usa")
            for code in selected_arrival_airports:
               # Get destination coordinates
                query_dest = "SELECT lat, lon, name FROM airports WHERE faa = ?"
                dest_df = pd.read_sql_query(query_dest, conn, params=(code,))
                if dest_df.empty:
                    continue
                dest = dest_df.iloc[0]

                # Use the selected departure airport from the sidebar
                origin_code = origin_airport
                query_origin_coords = "SELECT lat, lon FROM airports WHERE faa = ?"
                origin_df2 = pd.read_sql_query(query_origin_coords, conn, params=(origin_code,))
                if origin_df2.empty:
                    continue
                origin = origin_df2.iloc[0]
                fig.add_scattergeo(
                    lon=[origin["lon"], dest["lon"]],
                    lat=[origin["lat"], dest["lat"]],
                    mode="lines",
                    line=dict(width=2, color="red"),
                    name=f"{origin_code} → {code}"
                )
            st.plotly_chart(fig)
    
    elif tab == "Distance Analysis":
        st.header("Distance Analysis")
        st.plotly_chart(visuals.get("fig_hist_geo"))
        st.plotly_chart(visuals.get("fig_hist_euc"))
        st.plotly_chart(visuals.get("fig_distance_vs_arr_delay"))
        
    elif tab == "Flights by Day":
        st.header("Flights by Day")
        month = st.number_input("Month (1-12)", min_value=1, max_value=12, value=1)
        day = st.number_input("Day (1-31)", min_value=1, max_value=31, value=1)
        origin = origin_airport
        st.write(f"Selected Origin Airport: {origin}")
        if st.button("Get Daily Stats"):
            month_str = f"{int(month):02d}"
            day_str = f"{int(day):02d}"
            query_day = """
            SELECT *
            FROM flights
            WHERE strftime('%m', time_hour) = ? AND strftime('%d', time_hour) = ? AND origin = ?
            """
            df_day = pd.read_sql_query(query_day, conn, params=(month_str, day_str, origin))
            if df_day.empty:
                st.write("No flights found for the given date and origin.")
            else:
                query_day_stats = """
                SELECT
                    COUNT(*) AS total_flights,
                    COUNT(DISTINCT dest) AS unique_destinations,
                    (SELECT dest FROM flights GROUP BY dest ORDER BY COUNT(*) DESC LIMIT 1) AS most_freq_dest,
                    AVG(dep_delay_final) AS avg_dep_delay,
                    AVG(arr_delay_final) AS avg_arr_delay
                FROM flights
                WHERE strftime('%m', time_hour) = ? AND strftime('%d', time_hour) = ? AND origin = ?
                """
                df_day_stats = pd.read_sql_query(query_day_stats, conn, params=(month_str, day_str, origin))
                
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Total Flights", df_day_stats["total_flights"])
                col2.metric("Unique Destinations", df_day_stats["unique_destinations"])
                col5.metric("Most Frequent Destination", df_day_stats["most_freq_dest"].iloc[0])
                col3.metric("Avg Departure Delay (min)", f"{df_day_stats['avg_dep_delay'].iloc[0]:.2f}")
                col4.metric("Avg Arrival Delay (min)", f"{df_day_stats['avg_arr_delay'].iloc[0]:.2f}")
                dest_list = df_day["dest"].unique().tolist()
                placeholders = ",".join("?" * len(dest_list))
                query_dest_coords = f"SELECT faa, name, lat, lon FROM airports WHERE faa IN ({placeholders})"
                df_dest = pd.read_sql_query(query_dest_coords, conn, params=dest_list)
                fig_day = px.scatter_geo(df_dest, lat="lat", lon="lon", hover_name="name",
                                          title=f"Destinations on {month}/{day} from {origin}")
                st.plotly_chart(fig_day)
    
    elif tab == "Trajectory Statistics":
        st.header("Trajectory Statistics")
        # Use the sidebar-selected origin and destination airports
        origin_sel = origin_airport
        dest_sel = dest_airport[0] if dest_airport else None

        st.write(f"Selected Trajectory: {origin_sel} → {dest_sel}")

        if st.button("Analyze Trajectory"):
            query_trajectory = """
            SELECT 
                p.type,
                AVG(f.air_time_final) AS avg_air_time,
                AVG(f.dep_delay_final) AS avg_dep_delay,
                AVG(f.arr_delay_final) AS avg_arr_delay,
                AVG(f.geodesic_distance) AS avg_geodesic_distance
            FROM flights f
            LEFT JOIN planes p ON f.tailnum = p.tailnum
            WHERE f.origin = ? AND f.dest = ?
            """
            df_route = pd.read_sql_query(query_trajectory, conn, params=(origin_sel, dest_sel))
            if df_route.empty:
                st.write("No flights found for this trajectory.")
            else:
                st.write("Trajectory Analysis:")
                col1, col2, col3, col4= st.columns(4)
                col1.metric("Avg Air Time (min)", f"{df_route['avg_air_time'].iloc[0]:.2f}")
                col2.metric("Avg Departure Delay (min)", f"{df_route['avg_dep_delay'].iloc[0]:.2f}")
                col3.metric("Avg Arrival Delay (min)", f"{df_route['avg_arr_delay'].iloc[0]:.2f}")
                col4.metric("Avg Distance (km)", f"{df_route['avg_geodesic_distance'].iloc[0]:.2f}")
                
                col5 = st.columns(1)[0]
                col5.metric("Most Frequent Plane Type", df_route['type'].iloc[0])
    
    elif tab == "Manufacturer & Airline Statistics":
        st.header("Manufacturer & Airline Statistics")
        # Average Departure Delay per Airline
        query_airline = """
        SELECT a.name, AVG(f.dep_delay) AS avg_dep_delay
        FROM flights f
        JOIN airlines a ON f.carrier = a.carrier
        GROUP BY a.name
        """
        df_airline = pd.read_sql_query(query_airline, conn)
        fig_airline = px.bar(df_airline, x="name", y="avg_dep_delay",
                             title="Average Departure Delay per Airline",
                             labels={"avg_dep_delay": "Avg Dep Delay (min)", "name": "Airline"})
        st.plotly_chart(fig_airline)
        # Top 5 Manufacturers for a Destination
        dest_input = dest_airport[0] if dest_airport else None
        st.write(f"Selected destination airport: {dest_input}")
        if st.button("Get Manufacturer Stats"):
            query_manufacturer = """
            SELECT p.manufacturer, COUNT(*) AS count
            FROM flights f
            JOIN planes p ON f.tailnum = p.tailnum
            WHERE f.dest = ?
            GROUP BY p.manufacturer
            ORDER BY count DESC
            LIMIT 5
            """
            df_manuf = pd.read_sql_query(query_manufacturer, conn, params=(dest_input,))
            if df_manuf.empty:
                st.write(f"No data found for destination {dest_input}.")
            else:
                st.dataframe(df_manuf, column_config={"manufacturer": "Manufacturer", "count": "Number of Flights"})
    
    elif tab == "Plane Delay Analysis":
        st.header("Plane Delay Analysis")
        st.subheader("Flight Distance vs. Arrival Delay (All Planes)")
        st.plotly_chart(visuals.get("fig_distance_vs_arr_delay"))
        plane_types = sorted(list(visuals["wind_vs_delay_by_type"].keys()))
        selected_pt = st.selectbox("Select Plane Type for Detailed Analysis", plane_types)
        st.subheader(f"Wind Speed vs. Departure Delay for {selected_pt}")
        st.plotly_chart(visuals["wind_vs_delay_by_type"][selected_pt])
        st.subheader(f"Precipitation vs. Departure Delay for {selected_pt}")
        st.plotly_chart(visuals["precip_vs_delay_by_type"][selected_pt])
        st.subheader(f"Avg Departure Delay & Flight Speed by Airport for {selected_pt}")
        st.plotly_chart(visuals["delay_airport_speed_by_type"][selected_pt])
    
    conn.close()