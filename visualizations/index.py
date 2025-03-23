import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def create_all_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db):
    conn = sqlite3.connect(preprocessed_db)
    # Existing visualizations
    fig_world = px.scatter_geo(
        df_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        title="Airport Locations Worldwide",
    )
    fig_world.update_traces(customdata=df_airports["faa"])
    fig_world.update_layout(clickmode="event+select")
    
    df_us_airports = df_airports[df_airports["tzone"].astype(str).str.contains("America", na=False)]
    fig_us = px.scatter_geo(
        df_us_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        title="US Airports",
        scope="usa",
    )
    
    fig_alt = px.scatter_geo(
        df_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        color="alt",
        title="Airports by Altitude",
        color_continuous_scale="viridis",
    )
    
    fig_hist_euc = px.histogram(
        df_flights,
        x="euclidean_distance",
        nbins=50,
        title="Euclidean Distance Distribution (Flight Data)",
    )
    fig_hist_geo = px.histogram(
        df_flights,
        x="geodesic_distance",
        nbins=50,
        title="Geodesic Distance Distribution (Flight Data)",
    )
    
    df_flight_distance = (
        df_flights.groupby("dest")["geodesic_distance"]
        .mean()
        .reset_index(name="avg_geodesic_distance")
    )
    df_db_distance = pd.read_sql_query(
        """
        SELECT dest, AVG(distance) AS avg_flight_distance
        FROM flights
        GROUP BY dest;
        """,
        conn,
    )
    df_compare = pd.merge(df_flight_distance, df_db_distance, on="dest", how="left")
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
    
    dep_dt = pd.to_datetime(df_flights["dep_dt"], utc=True)
    arr_dt = pd.to_datetime(df_flights["arr_dt"], utc=True)
    df_flights["computed_duration"] = (arr_dt - dep_dt).dt.total_seconds() / 60
    fig_duration = px.scatter(
        df_flights,
        x="computed_duration",
        y="air_time",
        title="Computed Flight Duration vs. Recorded Air Time",
        labels={
            "computed_duration": "Computed Duration (min)",
            "air_time": "Air Time (min)",
        },
    )
    
    query = """
            SELECT 
                f.rowid,
                f.origin,
                f.dest,
                f.air_time,
                f.time_hour,
                f.bearing,
                w.wind_speed,
                w.wind_dir,
                w.precip
            FROM flights f
            JOIN weather w
            ON f.origin = w.origin
            AND f.time_hour = w.dt
            WHERE f.air_time_final IS NOT NULL;
            """
    df_merged_weather = pd.read_sql_query(query, conn)

    
    df_merged_weather["inner_product"] = df_merged_weather.apply(
        lambda row: row["wind_speed"] * np.cos(np.radians(row["bearing"] - row["wind_dir"])), axis=1
    )
    fig_inner_product = px.scatter(
        df_merged_weather,
        x="inner_product",
        y="air_time",
        title="Inner Product vs. Air Time",
        opacity=0.5,
        labels={
            "inner_product": "Inner Product (Flight Dir · Wind Vec)",
            "air_time": "Air Time (min)",
        },
    )
    corr_val = df_merged_weather["inner_product"].corr(df_merged_weather["air_time"])
    
    if "dep_delay" in df_flights.columns and "carrier" in df_flights.columns:
        df_airline_delay = pd.merge(df_flights, df_airlines, on="carrier", how="left")
        group_delay = (
            df_airline_delay.groupby("name")["dep_delay"]
            .mean()
            .reset_index()
            .sort_values("dep_delay", ascending=False)
        )
        fig_airline_delay = px.bar(
            group_delay,
            x="name",
            y="dep_delay",
            title="Average Departure Delay per Airline",
            labels={"dep_delay": "Avg Dep Delay (min)", "name": "Airline"},
        )
    else:
        fig_airline_delay = go.Figure()
        
    fig_distance_vs_arr_delay = px.scatter(
        df_flights,
        x="geodesic_distance",
        y="arr_delay_final",
        title="Flight Distance vs. Arrival Delay",
        labels={"geodesic_distance": "Geodesic Distance (km)", "arr_delay_final": "Arrival Delay (min)"},
        opacity=0.6,
    )
    
    plane_graph_query = """
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
                        p.*,
                        w.wind_speed,
                        w.wind_dir,
                        w.precip,
                        -- Compute flight speed (km/h) as: distance (km) * 60 / air_time (min)
                        (f.geodesic_distance * 60.0 / f.air_time_final) AS flight_speed
                    FROM flights f
                    LEFT JOIN planes p 
                        ON f.tailnum = p.tailnum
                    LEFT JOIN weather w 
                        ON f.time_hour = w.dt
                    WHERE f.air_time_final IS NOT NULL;
                    """
    df_plane_graph = pd.read_sql_query(plane_graph_query, conn)
    
    df_plane_graph["flight_speed"] = df_plane_graph.apply(
        lambda row: row["geodesic_distance"] * 60 / row["air_time_final"] if row["air_time_final"] > 0 else None, axis=1
    )
    
    plane_types = sorted(df_plane_graph["type"].dropna().unique())
    wind_vs_delay_by_type = {}
    precip_vs_delay_by_type = {}
    delay_airport_speed_by_type = {}
    
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
        
        group = subset.groupby("origin").agg(avg_delay=("dep_delay_final", "mean"),
                                            avg_speed=("flight_speed", "mean")).reset_index()
        fig_delay_airport_speed = px.scatter(
            group,
            x="origin",
            y="avg_delay",
            size="avg_speed",
            title=f"Avg Departure Delay by Airport & Avg Flight Speed for {pt}",
            labels={"origin": "Origin Airport", "avg_delay": "Avg Departure Delay (min)", "avg_speed": "Avg Flight Speed (km/h)"},
        )
        wind_vs_delay_by_type[pt] = fig_wind_vs_delay
        precip_vs_delay_by_type[pt] = fig_precip_vs_delay
        delay_airport_speed_by_type[pt] = fig_delay_airport_speed

    # --------------------------------------------------------------------------
    # Assemble all visualizations in a dictionary
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
        # New graphs:
        "fig_distance_vs_arr_delay": fig_distance_vs_arr_delay,
        "wind_vs_delay_by_type": wind_vs_delay_by_type,
        "precip_vs_delay_by_type": precip_vs_delay_by_type,
        "delay_airport_speed_by_type": delay_airport_speed_by_type,
    }
    return visuals
