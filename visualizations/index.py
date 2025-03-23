# visualizations/index.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def create_all_visualizations(conn):
    visuals = {}

    # --- World Airports Map ---
    query_airports = "SELECT faa, name, lat, lon, alt, tzone FROM airports"
    df_airports = pd.read_sql_query(query_airports, conn)
    fig_world = px.scatter_geo(
        df_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        title="Airport Locations Worldwide"
    )
    fig_world.update_traces(customdata=df_airports["faa"])
    visuals["fig_world"] = fig_world

    # --- US Airports Map ---
    query_us_airports = "SELECT faa, name, lat, lon, tzone FROM airports WHERE tzone LIKE '%America%'"
    df_us_airports = pd.read_sql_query(query_us_airports, conn)
    fig_us = px.scatter_geo(
        df_us_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        title="US Airports",
        scope="usa"
    )
    visuals["fig_us"] = fig_us

    # --- Altitude Map ---
    fig_alt = px.scatter_geo(
        df_airports,
        lat="lat",
        lon="lon",
        hover_name="name",
        color="alt",
        title="Airports by Altitude",
        color_continuous_scale="viridis"
    )
    visuals["fig_alt"] = fig_alt

    # --- Euclidean Distance Histogram ---
    query_euc = "SELECT euclidean_distance FROM flights WHERE euclidean_distance IS NOT NULL"
    df_euc = pd.read_sql_query(query_euc, conn)
    fig_hist_euc = px.histogram(
        df_euc,
        x="euclidean_distance",
        nbins=50,
        title="Euclidean Distance Distribution (Flight Data)"
    )
    visuals["fig_hist_euc"] = fig_hist_euc

    # --- Geodesic Distance Histogram ---
    query_geo = "SELECT geodesic_distance FROM flights WHERE geodesic_distance IS NOT NULL"
    df_geo = pd.read_sql_query(query_geo, conn)
    fig_hist_geo = px.histogram(
        df_geo,
        x="geodesic_distance",
        nbins=50,
        title="Geodesic Distance Distribution (Flight Data)"
    )
    visuals["fig_hist_geo"] = fig_hist_geo

    # --- Computed vs. DB Flight Distances ---
    query_compare = """
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
    """
    df_compare = pd.read_sql_query(query_compare, conn)
    fig_compare = px.scatter(
        df_compare,
        x="avg_geodesic_distance",
        y="avg_flight_distance",
        title="Computed vs. DB Flight Distances",
        opacity=0.6,
        labels={
            "avg_geodesic_distance": "Avg Computed Geodesic Distance (km)",
            "avg_flight_distance": "Avg Flight Distance (km)"
        }
    )
    visuals["fig_compare"] = fig_compare

    # --- Flight Duration vs. Recorded Air Time ---
    query_duration = """
    SELECT rowid,
           CAST((julianday(arr_dt) - julianday(dep_dt)) * 24 * 60 AS REAL) AS computed_duration,
           air_time
    FROM flights
    WHERE dep_dt IS NOT NULL AND arr_dt IS NOT NULL
    """
    df_duration = pd.read_sql_query(query_duration, conn)
    fig_duration = px.scatter(
        df_duration,
        x="computed_duration",
        y="air_time",
        title="Computed Flight Duration vs. Recorded Air Time",
        labels={"computed_duration": "Computed Duration (min)", "air_time": "Air Time (min)"}
    )
    visuals["fig_duration"] = fig_duration

    # --- Inner Product vs. Air Time ---
    # (Because SQLite lacks trig functions, we fetch needed columns and compute in Python)
    query_inner = """
    SELECT f.rowid, f.air_time, f.bearing, w.wind_speed, w.wind_dir
    FROM flights f
    JOIN weather w ON f.origin = w.origin AND f.time_hour = w.dt
    WHERE f.air_time_final IS NOT NULL
    """
    df_inner = pd.read_sql_query(query_inner, conn)
    df_inner["inner_product"] = df_inner["wind_speed"] * np.cos(np.deg2rad(df_inner["bearing"] - df_inner["wind_dir"]))
    fig_inner = px.scatter(
        df_inner,
        x="inner_product",
        y="air_time",
        title="Inner Product vs. Air Time",
        opacity=0.5,
        labels={"inner_product": "Inner Product (Flight Dir · Wind Vec)", "air_time": "Air Time (min)"}
    )
    visuals["fig_inner_product"] = fig_inner

    # --- Average Departure Delay per Airline ---
    query_airline_delay = """
    SELECT a.name, AVG(f.dep_delay) AS avg_dep_delay
    FROM flights f
    JOIN airlines a ON f.carrier = a.carrier
    GROUP BY a.name
    """
    df_airline_delay = pd.read_sql_query(query_airline_delay, conn)
    fig_airline_delay = px.bar(
        df_airline_delay,
        x="name",
        y="avg_dep_delay",
        title="Average Departure Delay per Airline",
        labels={"avg_dep_delay": "Avg Dep Delay (min)", "name": "Airline"}
    )
    visuals["fig_airline_delay"] = fig_airline_delay

    # --- Flight Distance vs. Arrival Delay ---
    query_delay_distance = "SELECT geodesic_distance, arr_delay_final FROM flights WHERE geodesic_distance IS NOT NULL AND arr_delay_final IS NOT NULL"
    df_delay_distance = pd.read_sql_query(query_delay_distance, conn)
    fig_distance_vs_arr_delay = px.scatter(
        df_delay_distance,
        x="geodesic_distance",
        y="arr_delay_final",
        title="Flight Distance vs. Arrival Delay",
        labels={"geodesic_distance": "Geodesic Distance (km)", "arr_delay_final": "Arrival Delay (min)"},
        opacity=0.6
    )
    visuals["fig_distance_vs_arr_delay"] = fig_distance_vs_arr_delay

    # --- Plane Type Analysis (by joining flights, planes, weather) ---
    query_plane = """
    SELECT f.rowid, f.origin, f.dest, f.air_time, f.air_time_final, f.time_hour, f.bearing,
           f.geodesic_distance, f.dep_delay_final, p.type, w.wind_speed, w.wind_dir, w.precip,
           (f.geodesic_distance * 60.0 / f.air_time_final) AS flight_speed
    FROM flights f
    LEFT JOIN planes p ON f.tailnum = p.tailnum
    LEFT JOIN weather w ON f.time_hour = w.dt
    WHERE f.air_time_final IS NOT NULL
    """
    df_plane = pd.read_sql_query(query_plane, conn)
    wind_vs_delay_by_type = {}
    precip_vs_delay_by_type = {}
    delay_airport_speed_by_type = {}

    for pt in sorted(df_plane["type"].dropna().unique()):
        subset = df_plane[df_plane["type"] == pt]
        fig_wind = px.scatter(
            subset,
            x="wind_speed",
            y="dep_delay_final",
            title=f"Wind Speed vs. Departure Delay ({pt})",
            labels={"wind_speed": "Wind Speed (km/h)", "dep_delay_final": "Departure Delay (min)"},
            opacity=0.6
        )
        wind_vs_delay_by_type[pt] = fig_wind

        fig_precip = px.scatter(
            subset,
            x="precip",
            y="dep_delay_final",
            title=f"Precipitation vs. Departure Delay ({pt})",
            labels={"precip": "Precipitation (mm)", "dep_delay_final": "Departure Delay (min)"},
            opacity=0.6
        )
        precip_vs_delay_by_type[pt] = fig_precip

        df_group = subset.groupby("origin").agg(
            avg_delay=("dep_delay_final", "mean"),
            avg_speed=("flight_speed", "mean")
        ).reset_index()
        fig_delay_airport = px.scatter(
            df_group,
            x="origin",
            y="avg_delay",
            size="avg_speed",
            title=f"Avg Dep Delay & Flight Speed by Airport ({pt})",
            labels={"origin": "Origin Airport", "avg_delay": "Avg Departure Delay (min)", "avg_speed": "Avg Flight Speed (km/h)"}
        )
        delay_airport_speed_by_type[pt] = fig_delay_airport

    visuals["wind_vs_delay_by_type"] = wind_vs_delay_by_type
    visuals["precip_vs_delay_by_type"] = precip_vs_delay_by_type
    visuals["delay_airport_speed_by_type"] = delay_airport_speed_by_type

    return visuals
