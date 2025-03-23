# dashboard/app.py

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from visualizations import index as vis

def run_dashboard():
    # Open connection to preprocessed database
    conn = sqlite3.connect("preprocessed_flights.db")
    
    st.title("Flights Dashboard")
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
            "Plane Type Analysis"
        ]
    )
    
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
    
    elif tab == "General Maps":
        st.header("General Maps")
        visuals = vis.create_all_visualizations(conn)
        st.subheader("World Airport Map")
        st.plotly_chart(visuals.get("fig_world"))
        st.subheader("US Airport Map")
        st.plotly_chart(visuals.get("fig_us"))
    
    elif tab == "Flight Routes":
        st.header("Flight Routes")
        # Select destination airports
        query_dests = "SELECT DISTINCT dest FROM flights"
        df_dests = pd.read_sql_query(query_dests, conn)
        dest_list = sorted(df_dests["dest"].tolist())
        selected_airports = st.multiselect("Select Destination Airports (FAA codes)", dest_list)
        if st.button("Plot Routes"):
            fig = px.scatter_geo()
            for code in selected_airports:
                # Get destination coordinates
                query_dest = "SELECT lat, lon, name FROM airports WHERE faa = ?"
                dest_df = pd.read_sql_query(query_dest, conn, params=(code,))
                if dest_df.empty:
                    continue
                dest = dest_df.iloc[0]
                # Get an origin for this route (first flight found)
                query_origin = "SELECT origin FROM flights WHERE dest = ? LIMIT 1"
                origin_df = pd.read_sql_query(query_origin, conn, params=(code,))
                if origin_df.empty:
                    continue
                origin_code = origin_df.iloc[0]["origin"]
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
        # Geodesic Distance Histogram
        query_hist = "SELECT geodesic_distance FROM flights WHERE geodesic_distance IS NOT NULL"
        df_hist = pd.read_sql_query(query_hist, conn)
        fig_hist = px.histogram(df_hist, x="geodesic_distance", nbins=50, title="Geodesic Distance Histogram")
        st.plotly_chart(fig_hist)
        # Delay vs. Distance Scatter
        query_scatter = "SELECT geodesic_distance, arr_delay_final FROM flights WHERE geodesic_distance IS NOT NULL AND arr_delay_final IS NOT NULL"
        df_scatter = pd.read_sql_query(query_scatter, conn)
        fig_scatter = px.scatter(df_scatter, x="geodesic_distance", y="arr_delay_final",
                                 title="Flight Distance vs. Arrival Delay",
                                 labels={"geodesic_distance": "Geodesic Distance (km)", "arr_delay_final": "Arrival Delay (min)"})
        st.plotly_chart(fig_scatter)
    
    elif tab == "Flights by Day":
        st.header("Flights by Day")
        month = st.number_input("Month (1-12)", min_value=1, max_value=12, value=1)
        day = st.number_input("Day (1-31)", min_value=1, max_value=31, value=1)
        query_origins = "SELECT DISTINCT origin FROM flights"
        df_origins = pd.read_sql_query(query_origins, conn)
        origin = st.selectbox("Select Origin Airport", sorted(df_origins["origin"].tolist()))
        if st.button("Get Daily Stats"):
            # Use strftime to filter dates (assuming time_hour stored in ISO format)
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
                total_flights = len(df_day)
                unique_dest = df_day["dest"].nunique()
                most_freq_dest = df_day["dest"].mode().iloc[0]
                st.write(f"Total Flights: {total_flights}, Unique Destinations: {unique_dest}, Most Frequent Destination: {most_freq_dest}")
                # Plot destination airports on a map
                dest_list = df_day["dest"].unique().tolist()
                placeholders = ",".join("?" * len(dest_list))
                query_dest_coords = f"SELECT faa, name, lat, lon FROM airports WHERE faa IN ({placeholders})"
                df_dest = pd.read_sql_query(query_dest_coords, conn, params=dest_list)
                fig_day = px.scatter_geo(df_dest, lat="lat", lon="lon", hover_name="name",
                                          title=f"Destinations on {month}/{day} from {origin}")
                st.plotly_chart(fig_day)
    
    elif tab == "Trajectory Statistics":
        st.header("Trajectory Statistics")
        query_orig = "SELECT DISTINCT origin FROM flights"
        df_orig = pd.read_sql_query(query_orig, conn)
        origin_sel = st.selectbox("Select Origin Airport", sorted(df_orig["origin"].tolist()))
        query_dest = "SELECT DISTINCT dest FROM flights WHERE origin = ?"
        df_dest = pd.read_sql_query(query_dest, conn, params=(origin_sel,))
        dest_sel = st.selectbox("Select Destination Airport", sorted(df_dest["dest"].tolist()))
        if st.button("Analyze Trajectory"):
            query_trajectory = """
            SELECT f.tailnum, p.type
            FROM flights f
            LEFT JOIN planes p ON f.tailnum = p.tailnum
            WHERE f.origin = ? AND f.dest = ?
            """
            df_route = pd.read_sql_query(query_trajectory, conn, params=(origin_sel, dest_sel))
            if df_route.empty:
                st.write("No flights found for this trajectory.")
            else:
                type_counts = df_route["type"].value_counts().to_dict()
                st.write("Plane Type Counts for this Trajectory:")
                st.write(type_counts)
    
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
        dest_input = st.selectbox("Select Destination", sorted(pd.read_sql_query("SELECT DISTINCT dest FROM flights", conn)["dest"].tolist()))
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
                st.write(df_manuf)
    
    elif tab == "Plane Type Analysis":
        st.header("Plane Type Analysis")
        visuals = vis.create_all_visualizations(conn)
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