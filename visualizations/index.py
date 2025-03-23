import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def create_all_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db):
    conn = sqlite3.connect(preprocessed_db)
    
    # Visualization 1: World Airports
    fig_world = px.scatter_geo(
        df_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        title="Airport Locations Worldwide",
    )
    fig_world.update_traces(customdata=df_airports["faa"])
    fig_world.update_layout(clickmode="event+select")

    # Visualization 2: US Airports
    df_us_airports = df_airports[df_airports["tzone"].astype(str).str.contains("America", na=False)]
    fig_us = px.scatter_geo(
        df_us_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        title="US Airports",
        scope="usa",
    )

    # Visualization 3: Airport Altitudes
    fig_alt = px.scatter_geo(
        df_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        color="alt",
        title="Airports by Altitude",
        color_continuous_scale="viridis",
    )

    # Histogram of Euclidean Distance (SQL not necessary, already in df_flights)
    fig_hist_euc = px.histogram(
        df_flights,
        x="euclidean_distance",
        nbins=50,
        title="Euclidean Distance Distribution (Flight Data)",
    )

    # Histogram of Geodesic Distance
    fig_hist_geo = px.histogram(
        df_flights,
        x="geodesic_distance",
        nbins=50,
        title="Geodesic Distance Distribution (Flight Data)",
    )

    # Visualization 4: Avg Distance Comparison (pure SQL)
    df_compare = pd.read_sql_query(
        """
        WITH computed_geodesic AS (
            SELECT dest, AVG(geodesic_distance) AS avg_geodesic_distance
            FROM flights
            GROUP BY dest
        ),
        db_distance AS (
            SELECT dest, AVG(distance) AS avg_flight_distance
            FROM flights
            GROUP BY dest
        )
        SELECT c.dest, c.avg_geodesic_distance, d.avg_flight_distance
        FROM computed_geodesic c
        LEFT JOIN db_distance d ON c.dest = d.dest;
        """,
        conn
    )

    fig_compare = px.scatter(
        df_compare,
        x="avg_geodesic_distance",
        y="avg_flight_distance",
        title="Computed vs. DB Flight Distances",
        opacity=0.6,
        labels={
            "avg_geodesic_distance": "Avg Computed Geodesic Distance (km)",
            "avg_flight_distance": "Avg Flight Distance (km)",
        },
    )

    # Visualization 5: Computed Duration vs Air Time (SQL)
    df_duration = pd.read_sql_query(
        """
        SELECT 
            rowid,
            CAST((JULIANDAY(arr_dt) - JULIANDAY(dep_dt)) * 24 * 60 AS REAL) AS computed_duration,
            air_time
        FROM flights
        WHERE dep_dt IS NOT NULL AND arr_dt IS NOT NULL;
        """,
        conn
    )

    fig_duration = px.scatter(
        df_duration,
        x="computed_duration",
        y="air_time",
        title="Computed Flight Duration vs. Recorded Air Time",
        labels={"computed_duration": "Computed Duration (min)", "air_time": "Air Time (min)"},
    )

    # Visualization 6: Inner Product of Wind and Flight Direction (SQL)
    df_merged_weather = pd.read_sql_query(
        """
        SELECT 
            f.rowid,
            f.air_time,
            f.bearing,
            w.wind_speed,
            w.wind_dir,
            (w.wind_speed * COS(RADIANS(f.bearing - w.wind_dir))) AS inner_product
        FROM flights f
        JOIN weather w
        ON f.origin = w.origin
        AND f.time_hour = w.dt
        WHERE f.air_time_final IS NOT NULL;
        """,
        conn
    )

    fig_inner_product = px.scatter(
        df_merged_weather,
        x="inner_product",
        y="air_time",
        title="Inner Product vs. Air Time",
        opacity=0.5,
        labels={"inner_product": "Inner Product (Flight Dir · Wind Vec)", "air_time": "Air Time (min)"},
    )
    corr_val = df_merged_weather["inner_product"].corr(df_merged_weather["air_time"])

    # Visualization 7: Average Departure Delay per Airline (SQL)
    df_airline_delay = pd.read_sql_query(
        """
        SELECT a.name, AVG(f.dep_delay) AS avg_dep_delay
        FROM flights f
        JOIN airlines a ON f.carrier = a.carrier
        GROUP BY a.name
        ORDER BY avg_dep_delay DESC;
        """,
        conn
    )

    fig_airline_delay = px.bar(
        df_airline_delay,
        x="name",
        y="avg_dep_delay",
        title="Average Departure Delay per Airline",
        labels={"avg_dep_delay": "Avg Dep Delay (min)", "name": "Airline"},
    )

    # Visualization 8: Flight Distance vs Arrival Delay (direct)
    fig_distance_vs_arr_delay = px.scatter(
        df_flights,
        x="geodesic_distance",
        y="arr_delay_final",
        title="Flight Distance vs. Arrival Delay",
        labels={"geodesic_distance": "Geodesic Distance (km)", "arr_delay_final": "Arrival Delay (min)"},
        opacity=0.6,
    )

    # Visualization 9: Plane & Weather Aggregates (SQL-heavy)
    df_plane_graph = pd.read_sql_query(
        """
        SELECT 
            f.rowid,
            f.origin,
            f.dest,
            f.air_time,
            f.air_time_final,
            f.time_hour,
            f.bearing,
            f.geodesic_distance,
            f.dep_delay_final,
            p.type,
            w.wind_speed,
            w.wind_dir,
            w.precip,
            (f.geodesic_distance * 60.0 / f.air_time_final) AS flight_speed
        FROM flights f
        LEFT JOIN planes p 
            ON f.tailnum = p.tailnum
        LEFT JOIN weather w 
            ON f.time_hour = w.dt
        WHERE f.air_time_final IS NOT NULL;
        """,
        conn
    )

    wind_vs_delay_by_type = {}
    precip_vs_delay_by_type = {}
    delay_airport_speed_by_type = {}

    plane_types = sorted(df_plane_graph["type"].dropna().unique())

    for pt in plane_types:
        subset = df_plane_graph[df_plane_graph["type"] == pt]

        fig_wind_vs_delay = px.scatter(
            subset,
            x="wind_speed",
            y="dep_delay_final",
            title=f"Wind Speed vs. Departure Delay for {pt}",
            labels={"wind_speed": "Wind Speed (km/h)", "dep_delay_final": "Departure Delay (min)"},
            opacity=0.6,
        )

        fig_precip_vs_delay = px.scatter(
            subset,
            x="precip",
            y="dep_delay_final",
            title=f"Precipitation vs. Departure Delay for {pt}",
            labels={"precip": "Precipitation (mm)", "dep_delay_final": "Departure Delay (min)"},
            opacity=0.6,
        )

        # Avg delay & speed per airport
        df_group = subset.groupby("origin").agg(
            avg_delay=("dep_delay_final", "mean"),
            avg_speed=("flight_speed", "mean")
        ).reset_index()

        fig_delay_airport_speed = px.scatter(
            df_group,
            x="origin",
            y="avg_delay",
            size="avg_speed",
            title=f"Avg Departure Delay by Airport & Avg Flight Speed for {pt}",
            labels={"origin": "Origin Airport", "avg_delay": "Avg Departure Delay (min)", "avg_speed": "Avg Flight Speed (km/h)"},
        )

        wind_vs_delay_by_type[pt] = fig_wind_vs_delay
        precip_vs_delay_by_type[pt] = fig_precip_vs_delay
        delay_airport_speed_by_type[pt] = fig_delay_airport_speed

    # Final dictionary
    visuals = {
        "fig_world": fig_world,
        "fig_us": fig_us,
        "fig_alt": fig_alt,
        "fig_hist_euc": fig_hist_euc,
        "fig_hist_geo": fig_hist_geo,
        "fig_compare": fig_compare,
        "fig_duration": fig_duration,
        "fig_airline_delay": fig_airline_delay,
        "fig_inner_product": fig_inner_product,
        "corr_val": corr_val,
        "fig_distance_vs_arr_delay": fig_distance_vs_arr_delay,
        "wind_vs_delay_by_type": wind_vs_delay_by_type,
        "precip_vs_delay_by_type": precip_vs_delay_by_type,
        "delay_airport_speed_by_type": delay_airport_speed_by_type,
    }
    return visuals