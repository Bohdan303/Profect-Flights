# ============================================================================
# Imports and Global Constants
# ============================================================================
import os
import sqlite3
import pickle
import datetime
import time
from math import radians, sin, cos, atan2, degrees, sqrt
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import concurrent

import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx

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
import streamlit as st


tf = TimezoneFinder()
BASE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
HOURLY_PARAMS = (
    "temperature_2m,dewpoint_2m,relativehumidity_2m,"
    "winddirection_10m,windspeed_10m,windgusts_10m,"
    "precipitation,surface_pressure,visibility"
)


# ============================================================================
# Time & Conversion Utilities
# ============================================================================
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


def ensure_datetime(val):
    """
    Ensures that the input value is a UTC-aware datetime object.
    - If already a datetime, returns it.
    - If a number, assumes it's a Unix timestamp (in seconds) and converts it.
    - If a string, first replaces a space with 'T' (if needed) before attempting ISO parsing.
    """
    if isinstance(val, datetime.datetime):
        return val
    if isinstance(val, (float, int)):
        return convert_time_hour_to_utc(val)
    if isinstance(val, str):
        try:
            # Replace space with 'T' for strict ISO format if needed.
            val_iso = val.replace(" ", "T")
            return datetime.datetime.fromisoformat(val_iso)
        except Exception:
            try:
                return convert_time_hour_to_utc(float(val))
            except Exception:
                return None
    return None


# ============================================================================
# Integrated Time Processing Functions
# ============================================================================

# vectorized part


# --------------------------
# 1. Time Conversion Helpers
# --------------------------
def vectorized_ensure_datetime(series):
    """
    Ensures that a Series of time values is converted to UTC-aware datetimes.
    Assumes the values are in an ISO-like format.
    """
    return pd.to_datetime(series, errors="coerce", utc=True)


def vectorized_clock_to_datetime(series, base_dates):
    """
    Vectorized conversion of HHMM clock values (as strings or numbers) into datetimes.
    - series: Series of HHMM values.
    - base_dates: Series of base dates (as datetime64[ns]) to combine with.

    For invalid values (hour > 23 or minute > 59), sets hour to 0 and adds one day.
    """
    # Convert values to string and remove trailing '.0' if present, then ensure 4 digits.
    s = series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    hours = s.str[:2].astype(int)
    minutes = s.str[2:].astype(int)
    base_dt = pd.to_datetime(base_dates)
    dt = base_dt + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")

    # Identify rows with invalid time values.
    invalid = (hours > 23) | (minutes > 59)
    if invalid.any():
        dt_invalid = (
            pd.to_datetime(base_dates[invalid])
            + pd.DateOffset(days=1)
            + pd.to_timedelta(minutes[invalid], unit="m")
        )
        dt.loc[invalid] = dt_invalid
    return dt


# --------------------------
# 2. Scheduled Time Computation
# --------------------------
def compute_sched_datetimes(df):
    """
    Computes scheduled departure and arrival datetimes (and base_date) from the
    HHMM fields using vectorized operations. Also adjusts for overnight scheduled arrivals.
    """
    # Convert base times
    df["time_hour"] = vectorized_ensure_datetime(df["time_hour"])
    df["base_date"] = df["time_hour"].dt.floor("D")

    # Compute scheduled departure and arrival datetimes
    df["sched_dep_dt"] = vectorized_clock_to_datetime(
        df["sched_dep_time"], df["base_date"]
    )
    df["sched_arr_dt"] = vectorized_clock_to_datetime(
        df["sched_arr_time"], df["base_date"]
    )

    # Adjust for overnight scheduled arrival times.
    overnight_mask = df["sched_arr_dt"] < df["sched_dep_dt"]
    df.loc[overnight_mask, "sched_arr_dt"] = df.loc[
        overnight_mask, "sched_arr_dt"
    ] + pd.Timedelta(days=1)

    # Compute scheduled air time (in minutes)
    df["computed_sched_air_time"] = (
        df["sched_arr_dt"] - df["sched_dep_dt"]
    ).dt.total_seconds() / 60.0
    return df


# --------------------------
# 3. Departure Processing
# --------------------------
def process_departure_times(df, tol_percent=10):
    """
    Processes departure times:
      - If 'dep_time' is available, converts it via the clock conversion.
      - Otherwise, computes departure datetime as scheduled departure plus reported dep_delay.
      - Computes the computed departure delay and “corrects” the reported delay if needed.
    """
    # Where dep_time is available, compute it.
    dep_time_mask = df["dep_time"].notnull()
    df.loc[dep_time_mask, "dep_dt"] = vectorized_clock_to_datetime(
        df.loc[dep_time_mask, "dep_time"], df.loc[dep_time_mask, "base_date"]
    )
    # Where dep_time is missing, use sched_dep_dt + dep_delay (defaulting missing dep_delay to 0).
    missing_dep_time = ~dep_time_mask
    df.loc[missing_dep_time, "dep_dt"] = df.loc[
        missing_dep_time, "sched_dep_dt"
    ] + pd.to_timedelta(df.loc[missing_dep_time, "dep_delay"].fillna(0), unit="m")

    overnight_mask = df["dep_dt"] < (df["time_hour"] - pd.to_timedelta(1, unit="h"))
    df.loc[overnight_mask, "dep_dt"] = df.loc[
        overnight_mask, "dep_dt"
    ] + pd.to_timedelta(1, unit="d")

    # Compute the computed departure delay (in minutes)
    df["computed_dep_delay"] = (
        df["dep_dt"] - df["sched_dep_dt"]
    ).dt.total_seconds() / 60.0

    # Final departure delay: if reported delay is missing, use computed;
    # if reported exists, use computed value when relative difference exceeds tol_percent.
    df["dep_delay_final"] = np.where(
        df["dep_delay"].isnull(), df["computed_dep_delay"], df["dep_delay"]
    )
    diff = abs(df["computed_dep_delay"] - df["dep_delay_final"])
    relative_diff = np.where(
        abs(df["computed_dep_delay"]) > 0, diff / abs(df["computed_dep_delay"]) * 100, 0
    )
    adjust_mask = relative_diff > tol_percent
    df.loc[adjust_mask, "dep_delay_final"] = df.loc[adjust_mask, "computed_dep_delay"]
    return df


# --------------------------
# 4. Arrival Processing
# --------------------------
def process_arrival_times(df, tol_percent=10):
    """
    Processes arrival times using similar logic as departure times.
    """
    # Where arr_time is available, convert it.
    arr_time_mask = df["arr_time"].notnull()
    df.loc[arr_time_mask, "arr_dt"] = vectorized_clock_to_datetime(
        df.loc[arr_time_mask, "arr_time"], df.loc[arr_time_mask, "base_date"]
    )
    # Where arr_time is missing, use sched_arr_dt + arr_delay.
    missing_arr_time = ~arr_time_mask
    df.loc[missing_arr_time, "arr_dt"] = df.loc[
        missing_arr_time, "sched_arr_dt"
    ] + pd.to_timedelta(df.loc[missing_arr_time, "arr_delay"].fillna(0), unit="m")

    overnight_mask = df["arr_dt"] < (df["time_hour"] - pd.to_timedelta(1, unit="h") + pd.to_timedelta(df["computed_sched_air_time"], unit="m"))
    df.loc[overnight_mask, "arr_dt"] = df.loc[
        overnight_mask, "arr_dt"
    ] + pd.to_timedelta(1, unit="d")

    # Compute computed arrival delay (in minutes)
    df["computed_arr_delay"] = (
        df["arr_dt"] - df["sched_arr_dt"]
    ).dt.total_seconds() / 60.0

    # Final arrival delay: if reported is missing, use computed; otherwise adjust if difference is too high.
    df["arr_delay_final"] = np.where(
        df["arr_delay"].isnull(), df["computed_arr_delay"], df["arr_delay"]
    )
    diff = abs(df["computed_arr_delay"] - df["arr_delay_final"])
    relative_diff = np.where(
        abs(df["computed_arr_delay"]) > 0, diff / abs(df["computed_arr_delay"]) * 100, 0
    )
    adjust_mask = relative_diff > tol_percent
    df.loc[adjust_mask, "arr_delay_final"] = df.loc[adjust_mask, "computed_arr_delay"]
    return df


# --------------------------
# 5. Overnight Adjustment & Air Time Calculation
# --------------------------
def adjust_actual_overnight(df):
    """
    For rows where the computed arrival datetime is before the departure,
    adds one day to the arrival datetime.
    """
    mask = df["arr_dt"] < df["dep_dt"]
    df.loc[mask, "arr_dt"] = df.loc[mask, "arr_dt"] + pd.Timedelta(days=1)
    return df


def compute_air_time(df, tol_percent=10):
    """
    Computes the actual air time (in minutes) from dep_dt and arr_dt and adjusts
    the reported air_time if the relative difference exceeds tol_percent.
    """
    df["computed_air_time"] = (df["arr_dt"] - df["dep_dt"]).dt.total_seconds() / 60.0
    df["air_time_final"] = np.where(
        df["air_time"].isnull(), df["computed_air_time"], df["air_time"]
    )
    diff = abs(df["computed_air_time"] - df["air_time_final"])
    relative_diff = np.where(
        abs(df["computed_air_time"]) > 0, diff / abs(df["computed_air_time"]) * 100, 0
    )
    adjust_mask = relative_diff > tol_percent
    df.loc[adjust_mask, "air_time_final"] = df.loc[adjust_mask, "computed_air_time"]
    return df


# --------------------------
# 6. Master Processing Function (Vectorized)
# --------------------------
def process_all_time_fields_vectorized(df, tol_percent=10):
    """
    Processes all time-related fields on the entire DataFrame using vectorized operations.
    It computes scheduled datetimes, processes departure and arrival times,
    adjusts for overnight actual flights, and computes the final air time.
    """
    df = compute_sched_datetimes(df)
    df = process_departure_times(df, tol_percent)
    df = process_arrival_times(df, tol_percent)
    df = adjust_actual_overnight(df)
    df = compute_air_time(df, tol_percent)

    # Optionally, you can assemble a summary status DataFrame or dictionary here.
    # For example, you might add columns with the computed delays and air times.
    return df


# --------------------------
# 6. Master Processing Function (Vectorized) (Multithreaded)
# --------------------------


def process_all_time_fields_vectorized_multithreaded(df, tol_percent=10, n_threads=5):
    """
    Processes all time-related fields on the entire DataFrame using a multithreaded vectorized approach.

    The DataFrame is split into n_threads chunks. Each chunk is processed using the
    vectorized function `process_all_time_fields_vectorized`, and then the results are concatenated.
    """
    # Split the DataFrame into approximately equal chunks.
    chunks = np.array_split(df, n_threads)

    # Worker function that processes a chunk using the vectorized approach.
    def worker_vectorized(chunk, tol_percent):
        return process_all_time_fields_vectorized(chunk, tol_percent)

    results = []
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [
            executor.submit(worker_vectorized, chunk, tol_percent) for chunk in chunks
        ]
        for future in futures:
            results.append(future.result())

    # Concatenate the processed chunks back into a single DataFrame.
    return pd.concat(results)


# ============================================================================
# Utility Functions Used in Later Sections
# ============================================================================
def use_us_scope(selected_airports, df_airports):
    """
    Given a list of selected airport FAA codes, returns True if all airports are in the United States.
    Assumes that the 'country' column in df_airports contains the country name.
    """
    for code in selected_airports:
        row = df_airports[df_airports["faa"] == code]
        if not row.empty and row.iloc[0]["country"] != "United States":
            return False
    return True


def analyze_weather_effects(df_flights, df_weather):
    """
    Analyzes how weather variables affect delays over the year.
    Ensures that flight and weather time columns are datetimelike.
    Returns a DataFrame with average departure delay and average temperature by month.
    """
    df_flights["time_hour"] = df_flights["time_hour"].apply(ensure_datetime)
    if "dt" not in df_weather.columns:
        df_weather["dt"] = df_weather["time_hour"].apply(convert_time_hour_to_utc)
    else:
        df_weather["dt"] = df_weather["dt"].apply(ensure_datetime)
    df_flights["month"] = df_flights["time_hour"].dt.month
    delay_by_month = df_flights.groupby("month")["dep_delay"].mean().reset_index()
    df_weather["month"] = df_weather["dt"].dt.month
    temp_by_month = df_weather.groupby("month")["temp"].mean().reset_index()
    analysis = pd.merge(delay_by_month, temp_by_month, on="month", how="left")
    return analysis


def plot_weather_analysis(analysis_df):
    """
    Returns a line chart showing average departure delay and temperature by month.
    """
    fig = px.line(
        analysis_df,
        x="month",
        y=["dep_delay", "temp"],
        labels={"value": "Average Value", "month": "Month"},
        title="Average Departure Delay and Temperature by Month",
    )
    return fig


def calculate_inner_product(bearing, wind_dir, wind_speed):
    """
    Calculates the inner (dot) product between the flight direction vector and wind vector.
    Returns: wind_speed * cos((bearing - wind_dir) in radians).
    """
    return wind_speed * np.cos(np.radians(bearing) - np.radians(wind_dir))


# ============================================================================
# Database Loading and Saving
# ============================================================================
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_flights_time_hour ON flights(time_hour)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_planes_tailnum ON planes(tailnum)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_weather_time_hour ON weather(time_hour)"
    )
    conn.commit()

    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
    df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
    df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
    df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)

    return conn, df_airports, df_flights, df_planes, df_weather, df_airlines


def save_preprocessed_data(
    df_airports,
    df_flights,
    df_planes,
    df_weather,
    df_airlines,
    output_db="preprocessed_flights.db",
):
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


# ============================================================================
# Airport Preprocessing
# ============================================================================
def augment_airports_with_missing(df_airports, df_flights):
    """Augments airports table with FAA codes from flights that are missing in the airports table."""
    flights_dest = set(df_flights["dest"].unique())
    airports_faa = set(df_airports["faa"].unique())
    missing_codes = flights_dest - airports_faa
    if not missing_codes:
        print("No missing airports found.")
        return df_airports
    print("Missing airports detected:", missing_codes)
    try:
        from airportsdata import load

        airports_dict = load("IATA")
    except ImportError:
        print(
            "airportsdata module not available. Install it with 'pip install airportsdata'"
        )
        return df_airports
    new_rows = []
    for code in missing_codes:
        if code in airports_dict:
            info = airports_dict[code]
            new_row = {
                "faa": code,
                "name": info.get("name", ""),
                "lat": info.get("lat", None),
                "lon": info.get("lon", None),
                "alt": info.get("elevation", None),
                "tz": np.nan,
                "dst": np.nan,
                "tzone": np.nan,
            }
            new_rows.append(new_row)
        else:
            print(f"No external data found for missing airport code: {code}")
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_airports = pd.concat([df_airports, df_new], ignore_index=True)
        print(
            "Augmented airports table with missing data for codes:",
            sorted(missing_codes),
        )
    return df_airports


def compute_timezone_info_for_missing(df_airports):
    """Computes timezone info (tz, dst, tzone) for airports missing this data."""
    for col in ["tz", "dst", "tzone"]:
        if col not in df_airports.columns:
            df_airports[col] = None

    def compute_info_for_row(row):
        tz = tf.timezone_at(lng=row["lon"], lat=row["lat"])
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
        return pd.Series([tz_offset, dst_active, tz], index=["tz", "dst", "tzone"])

    missing_mask = df_airports[["tz", "dst", "tzone"]].isna().any(axis=1)
    df_airports.loc[missing_mask, ["tz", "dst", "tzone"]] = df_airports.loc[
        missing_mask
    ].apply(compute_info_for_row, axis=1)
    return df_airports


def country_to_continent(country_code):
    """Converts a 2-letter country code to a continent name."""
    try:
        continent_code = pc.country_alpha2_to_continent_code(country_code)
        mapping = {
            "AF": "Africa",
            "AS": "Asia",
            "EU": "Europe",
            "NA": "North America",
            "OC": "Oceania",
            "SA": "South America",
            "AN": "Antarctica",
        }
        return mapping.get(continent_code, "Unknown")
    except Exception:
        return "Unknown"


def add_location_info_to_airports(df_airports):
    """Adds reverse geocoded location info (continent, country, city) to airports."""
    coords = list(zip(df_airports["lat"], df_airports["lon"]))
    results = rg.search(coords, mode=2)
    continents, countries, cities = [], [], []
    for res in results:
        city = res.get("name", "Unknown")
        country_code = res.get("cc", "Unknown")
        continent = country_to_continent(country_code)
        try:
            country_obj = pycountry.countries.get(alpha_2=country_code)
            country_name = country_obj.name if country_obj else country_code
        except Exception:
            country_name = country_code
        continents.append(continent)
        countries.append(country_name)
        cities.append(city)
    df_airports["continent"] = continents
    df_airports["country"] = countries
    df_airports["city"] = cities
    return df_airports


def preprocess_airports(df_airports, df_flights):
    """Preprocesses the airports table."""
    df_airports = augment_airports_with_missing(df_airports, df_flights)
    df_airports = compute_timezone_info_for_missing(df_airports)
    df_airports = add_location_info_to_airports(df_airports)
    return df_airports


# ============================================================================
# Flight Preprocessing
# ============================================================================
# (Note: The previous separate fill functions are now integrated in process_all_time_fields)
def change_sched_time_to_datetime(df):
    """
    Replace the raw scheduled times (in HHMM format) with datetime objects using the date from 'time_hour',
    and update actual times (dep_time and arr_time) as scheduled time plus delay.
    """
    df["time_hour"] = df["time_hour"].apply(
        lambda x: (
            x
            if isinstance(x, (datetime.datetime, datetime.date))
            else datetime.datetime.fromisoformat(x)
        )
    )

    def combine_time(row, col):
        base_date = row["time_hour"].date()
        try:
            time_val = int(row[col])
        except Exception:
            return None
        time_str = f"{time_val:04d}"
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        return datetime.datetime.combine(
            base_date, datetime.time(hour=hour, minute=minute)
        )

    df["sched_dep_time"] = df.apply(
        lambda row: combine_time(row, "sched_dep_time"), axis=1
    )
    df["sched_arr_time"] = df.apply(
        lambda row: combine_time(row, "sched_arr_time"), axis=1
    )

    def adjust_arrival(row):
        dep = row["sched_dep_time"]
        arr = row["sched_arr_time"]
        if dep and arr and arr < dep:
            return arr + datetime.timedelta(days=1)
        return arr

    df["sched_arr_time"] = df.apply(adjust_arrival, axis=1)
    if "dep_delay" in df.columns and "dep_time" in df.columns:
        df["dep_time"] = df["sched_dep_time"] + pd.to_timedelta(
            df["dep_delay"], unit="m"
        )
    if "arr_delay" in df.columns and "arr_time" in df.columns:
        df["arr_time"] = df["sched_arr_time"] + pd.to_timedelta(
            df["arr_delay"], unit="m"
        )
    return df


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
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 6371 * c


def compute_flight_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate the initial bearing between two points on the Earth.

    Parameters:
        lat1, lon1: Latitude and longitude of the first point.
        lat2, lon2: Latitude and longitude of the second point.

    Returns:
        float: Initial bearing in degrees.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    y = sin(dlon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    return (degrees(atan2(y, x)) + 360) % 360


def compute_flight_distances(df_flights, df_airports):
    """
    Computes the Euclidean and Geodesic distances for each flight based on the origin and destination
    airport coordinates, and computes the flight bearing.
    """
    origin_coords = df_airports[["faa", "lat", "lon"]].rename(
        columns={"faa": "origin", "lat": "origin_lat", "lon": "origin_lon"}
    )
    dest_coords = df_airports[["faa", "lat", "lon"]].rename(
        columns={"faa": "dest", "lat": "dest_lat", "lon": "dest_lon"}
    )
    df_flights = df_flights.merge(origin_coords, on="origin", how="left")
    df_flights = df_flights.merge(dest_coords, on="dest", how="left")
    df_flights["euclidean_distance"] = np.sqrt(
        (df_flights["dest_lat"] - df_flights["origin_lat"]) ** 2
        + (df_flights["dest_lon"] - df_flights["origin_lon"]) ** 2
    )
    df_flights["geodesic_distance"] = df_flights.apply(
        lambda row: haversine_distance(
            row["origin_lat"], row["origin_lon"], row["dest_lat"], row["dest_lon"]
        ),
        axis=1,
    )
    df_flights["bearing"] = df_flights.apply(
        lambda row: compute_flight_bearing(
            row["origin_lat"], row["origin_lon"], row["dest_lat"], row["dest_lon"]
        ),
        axis=1,
    )
    df_flights.drop(
        columns=["origin_lat", "origin_lon", "dest_lat", "dest_lon"], inplace=True
    )
    return df_flights


def preprocess_flights(df_flights, df_airports):
    """Preprocesses the flights table, including integrated time processing and distance computations."""
    df_flights.drop_duplicates(inplace=True)
    if "time_hour" in df_flights.columns:
        df_flights["time_hour"] = df_flights["time_hour"].apply(ensure_datetime)
    # Process all time fields (using our integrated function with percentage tolerance).
    # vectorized and multithreaded
    df_flights = process_all_time_fields_vectorized_multithreaded(
        df_flights, tol_percent=10
    )

    # Also update scheduled times based on the new conversion function (if needed).
    df_flights = change_sched_time_to_datetime(df_flights)
    df_flights = compute_flight_distances(df_flights, df_airports)
    return df_flights


def compute_local_arrival(df, df_airports):
    """Computes local arrival time using timezone offsets from the airports table.
    Here, we use the processed actual arrival datetime (arr_dt) and add the airport's offset.
    """
    tz_mapping = df_airports.set_index("faa")["tz"].to_dict()
    df["dest_offset"] = df["dest"].map(tz_mapping).fillna(0)
    df["local_arrival"] = df["arr_dt"] + pd.to_timedelta(df["dest_offset"], unit="h")
    df.drop(columns=["dest_offset"], inplace=True)
    return df


# ============================================================================
# Plane Preprocessing (Manufacture Year Inference & Speed Update)
# ============================================================================
def infer_manufacture_year(df_planes):
    """
    For each plane model, fills missing 'year' values using the mode (most frequent) year.
    """

    def fill_missing_with_mode(series):
        non_null = series.dropna()
        if non_null.empty:
            return series
        mode_val = non_null.mode().iloc[0]
        return series.fillna(mode_val)

    df_planes["year"] = df_planes.groupby("model")["year"].transform(
        fill_missing_with_mode
    )
    return df_planes


def update_plane_speed(df_flights, df_planes):
    """
    Computes average speed (km/h) from flight data for each tailnum and updates the 'speed'
    column in the planes DataFrame where missing.
    """
    valid = df_flights[df_flights["air_time"] > 0]
    df_speed = (
        valid.groupby("tailnum")
        .apply(lambda x: (60.0 * x["distance"].sum()) / x["air_time"].sum())
        .reset_index(name="avg_speed")
    )
    df_planes = df_planes.merge(df_speed, on="tailnum", how="left")
    df_planes["speed"] = df_planes.apply(
        lambda row: (
            row["avg_speed"]
            if pd.isnull(row["speed"]) or row["speed"] == ""
            else row["speed"]
        ),
        axis=1,
    )
    df_planes.drop(columns=["avg_speed"], inplace=True)
    return df_planes


def preprocess_planes(df_planes, df_flights):
    """Preprocesses the planes table by inferring manufacture year and updating speed."""
    df_planes["year"] = pd.to_numeric(df_planes["year"], errors="coerce")
    df_planes = infer_manufacture_year(df_planes)
    df_planes = update_plane_speed(df_flights, df_planes)
    return df_planes


# ============================================================================
# Weather Preprocessing
# ============================================================================
def merge_airport_data(df_weather, df_airports):
    """Merges airport info into the weather table."""
    df_airports_subset = df_airports[["faa", "lat", "lon", "tz"]]
    return df_weather.merge(
        df_airports_subset,
        left_on="origin",
        right_on="faa",
        how="left",
        suffixes=("", "_airport"),
    )


def convert_time_columns(df_weather):
    """Converts the time_hour column in weather to a UTC datetime column stored in 'dt'."""
    df_weather["dt"] = df_weather["time_hour"].apply(convert_time_hour_to_utc)
    return df_weather


def get_weather_data_with_backoff(params, max_retries=5):
    """Makes an API request for weather data with exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
        except Exception as e:
            print(f"Request exception: {e}")
            time.sleep(2**attempt)
            continue
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else 2**attempt
            print(f"429 received. Retrying after {wait} seconds...")
            time.sleep(wait)
        else:
            print(f"API request failed with status code {response.status_code}")
            time.sleep(2**attempt)
    return None


def process_origin_weather(origin, df_weather, df_airports):
    """For a given origin, updates missing weather data using the API."""
    try:
        airport_info = df_airports[df_airports["faa"] == origin].iloc[0]
    except IndexError:
        print(f"Origin {origin} not found in airports data.")
        return pd.DataFrame()
    tz = airport_info.get("tz") or 0
    tzone = airport_info.get("tzone")
    lat = airport_info["lat"]
    lon = airport_info["lon"]
    subset = df_weather[df_weather["origin"] == origin].copy()
    if subset.empty:
        return subset
    subset["local_dt"] = subset["dt"] + pd.to_timedelta(tz, unit="h")
    start_date = subset["local_dt"].min().strftime("%Y-%m-%d")
    end_date = subset["local_dt"].max().strftime("%Y-%m-%d")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HOURLY_PARAMS,
        "timezone": tzone,
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
        "visibility": "visib",
    }
    for idx, row in subset.iterrows():
        target_time = row["local_dt"].strftime("%Y-%m-%dT%H:00")
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
    missing_mask = df_weather["temp"].isnull()
    missing_df = df_weather[missing_mask].copy()
    unique_origins = missing_df["origin"].unique()
    if len(unique_origins) <= 4:
        updated_subsets = []
        with ThreadPoolExecutor(max_workers=len(unique_origins)) as executor:
            futures = {
                executor.submit(
                    process_origin_weather, origin, df_weather, df_airports
                ): origin
                for origin in unique_origins
            }
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
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    process_origin_weather,
                    chunk["origin"].iloc[0],
                    df_weather,
                    df_airports,
                ): i
                for i, chunk in enumerate(chunks)
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    updated_chunks.append(future.result())
                except Exception as e:
                    print(f"Error processing chunk: {e}")
        for chunk in updated_chunks:
            if not chunk.empty:
                df_weather.loc[chunk.index, :] = chunk
    df_weather.drop(columns=["faa"], inplace=True, errors="ignore")
    return df_weather


# ============================================================================
# Airlines Preprocessing
# ============================================================================
def preprocess_airlines(df_airlines):
    """Fills missing airline names with 'Unknown'."""
    if "name" in df_airlines.columns:
        missing_count = df_airlines["name"].isnull().sum()
        if missing_count > 0:
            print(f"Filling {missing_count} missing values in 'name' with 'Unknown'.")
            df_airlines["name"] = df_airlines["name"].fillna("Unknown")
    else:
        print("The 'name' column is not present in airlines data.")
    return df_airlines


# ============================================================================
# Preprocessing Orchestration
# ============================================================================
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
    df_flights = preprocess_flights(df_flights, df_airports)
    print("Missing values in flights data:\n", df_flights.isnull().sum())
    df_planes = preprocess_planes(df_planes, df_flights)
    print("Missing values in planes data:\n", df_planes.isnull().sum())
    df_weather = preprocess_weather(df_weather, df_airports)
    print("Missing values in weather data:\n", df_weather.isnull().sum())

    weather_analysis = analyze_weather_effects(df_flights, df_weather)
    print("Weather Analysis by Month:\n", weather_analysis)

    df_flights = compute_local_arrival(df_flights, df_airports)

    tables = {
        "airports": df_airports,
        "flights": df_flights,
        "planes": df_planes,
        "weather": df_weather,
        "airlines": df_airlines,
    }
    print_missing_values(tables)
    return df_airports, df_flights, df_planes, df_weather, df_airlines


# ============================================================================ 
# Visualization Function (Precomputing all graphs) 
# ============================================================================ 
@st.cache_data
def create_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db):
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
    
    # df_sample = pd.read_sql_query(
    # """
    # SELECT rowid, origin, dest, air_time, time_hour, bearing, day, month
    # FROM flights
    # WHERE air_time_final IS NOT NULL
    # """,
    # conn,
    # )

    # # Ensure the time columns are datetime.
    # df_sample["time_hour"] = ensure_datetime(df_sample["time_hour"])
    # df_weather["dt"] = ensure_datetime(df_weather["dt"])

    # # Get the list of origins (for example, JFK, EWR, LGA—or all unique origins)
    # origins = df_sample["origin"].unique().tolist()

    # # Split flight data by origin.
    # df_origin_dict = {origin: df_sample[df_sample["origin"] == origin].copy() for origin in origins}

    # # Split weather data by origin.
    # weather_by_origin = {origin: df_weather[df_weather["origin"] == origin].copy() for origin in origins}

    # # For each origin, split the weather data into dictionaries by month and day.
    # weather_by_origin_month_day = {}
    # for origin in origins:
    #     weather_by_origin_month_day[origin] = {}
    #     for month in range(1, 13):
    #         # Filter for the given origin and month.
    #         df_weather_month = weather_by_origin[origin][weather_by_origin[origin]["month"] == month]
    #         # Now split by day (for all days 1 to 31; days with no data will be empty)
    #         weather_by_origin_month_day[origin][month] = {
    #             day: df_weather_month[df_weather_month["day"] == day].copy()
    #             for day in range(1, 32)
    #         }

    # # Define a function that merges flight and weather data for a given origin, month, and day.
    # def merge_origin_month_day(origin, month, day):
    #     # Get flight data for the origin, filtering by month and day.
    #     df_origin = df_origin_dict[origin]
    #     df_origin = df_origin[(df_origin["month"] == month) & (df_origin["day"] == day)]
    #     if df_origin.empty:
    #         # No flights for this combination; return an empty DataFrame.
    #         return pd.DataFrame()

    #     # Get weather data for the given origin, month, and day.
    #     weather_subset = weather_by_origin_month_day[origin][month][day][["dt", "wind_speed", "wind_dir", "precip"]]
    #     if weather_subset.empty:
    #         return pd.DataFrame()

    #     # Merge the flight data with the weather data on the exact time match.
    #     merged = pd.merge(
    #         df_origin,
    #         weather_subset,
    #         left_on="time_hour",
    #         right_on="dt",
    #         how="left"
    #     )
    #     # Add columns to record the origin, month, and day for the merge.
    #     merged["merge_origin"] = origin
    #     merged["merge_month"] = month
    #     merged["merge_day"] = day
    #     return merged

    # # Use a ThreadPoolExecutor to merge in parallel.
    # results = []
    # # Estimate total tasks: len(origins)*12*31. You might limit max_workers based on your system.
    # total_tasks = len(origins) * 12 * 31
    # with ThreadPoolExecutor(max_workers=24) as executor:
    #     futures = []
    #     for origin in origins:
    #         for month in range(1, 13):
    #             for day in range(1, 32):
    #                 futures.append(executor.submit(merge_origin_month_day, origin, month, day))
    #     for future in concurrent.futures.as_completed(futures):
    #         result = future.result()
    #         # Append non-empty results only to reduce final concatenation overhead.
    #         if not result.empty:
    #             results.append(result)

    # # Concatenate all merged chunks.
    # df_merged_weather = pd.concat(results, ignore_index=True)
    
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
    
    # --------------------------------------------------------------------------
    # New Graphs
    # --------------------------------------------------------------------------
    # 1. Flight Distance vs. Arrival Delay (using arr_delay_final)
    fig_distance_vs_arr_delay = px.scatter(
        df_flights,
        x="geodesic_distance",
        y="arr_delay_final",
        title="Flight Distance vs. Arrival Delay",
        labels={"geodesic_distance": "Geodesic Distance (km)", "arr_delay_final": "Arrival Delay (min)"},
        opacity=0.6,
    )
    
    # # Prepare a merged dataframe for plane-type analysis:
    # df_plane_graph = pd.merge(df_flights, df_planes, on="tailnum", how="left")
    # # Ensure dt is a datetime column and unique
    # df_weather["time_hour"] = ensure_datetime(df_weather["dt"])
    # df_weather_unique = df_weather

    # # Ensure flight time_hour is also datetime
    # df_plane_graph["time_hour"] = ensure_datetime(df_plane_graph["time_hour"])

    # # Join on the time_hour column (which is not the index) with the weather index
    # #df_plane_graph = df_plane_graph.join(df_weather_unique, on="time_hour", how="left")
    # df_plane_graph = pd.merge(df_plane_graph,df_weather_unique, on="time_hour", how="left")
    # # Compute flight speed (km/h) from geodesic_distance and air_time_final (in minutes)
    
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
    
    # For each plane type, compute:
    plane_types = sorted(df_plane_graph["type"].dropna().unique())
    wind_vs_delay_by_type = {}
    precip_vs_delay_by_type = {}
    delay_airport_speed_by_type = {}
    
    for pt in plane_types:
        subset = df_plane_graph[df_plane_graph["type"] == pt]
        # Graph B: Wind Speed vs. Departure Delay
        fig_wind_vs_delay = px.scatter(
            subset,
            x="wind_speed",
            y="dep_delay_final",
            title=f"Wind Speed vs. Departure Delay for {pt}",
            labels={"wind_speed": "Wind Speed (km/h)", "dep_delay_final": "Departure Delay (min)"},
            opacity=0.6,
        )
        # Graph C: Precipitation vs. Departure Delay
        fig_precip_vs_delay = px.scatter(
            subset,
            x="precip",
            y="dep_delay_final",
            title=f"Precipitation vs. Departure Delay for {pt}",
            labels={"precip": "Precipitation (mm)", "dep_delay_final": "Departure Delay (min)"},
            opacity=0.6,
        )
        # Graph D: Average Delay by Airport with marker size indicating average flight speed
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
    visualizations = {
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
    return visualizations

# ============================================================================ 
# Dashboard Using Streamlit (Updated to use precomputed visuals) 
# ============================================================================ 
def run_dashboard(df_airports, df_flights, df_planes, df_weather, df_airlines, conn, visuals):
    st.title("Flights Dashboard")

    # Sidebar tab selection (reorganized)
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

    # ---------------------------
    # General Statistics Tab
    # ---------------------------
    if tab == "General Statistics":
        st.header("General Statistics")
        # Time Zone Chart: Group flights by destination airport time zone (using df_airports)
        df_tz = pd.merge(
            df_flights, df_airports[["faa", "tz"]],
            left_on="dest", right_on="faa", how="left"
        )
        tz_counts = df_tz.groupby("tz").agg(avg_dep_delay=("dep_delay_final", "mean")).reset_index()
        fig_tz = px.bar(tz_counts, x="tz", y="avg_dep_delay",
                        title="Average Departure Delay by Destination Time Zone",
                        labels={"tz": "Time Zone", "avg_dep_delay": "Avg Departure Delay (min)"})
        st.plotly_chart(fig_tz)

        # Inner Product vs Air Time (precomputed)
        st.plotly_chart(visuals["fig_inner_product"])
        st.write(f"Correlation: {visuals['corr_val']:.2f}")

        # Delay by Airport Chart: Group by origin airport and average departure delay
        df_delay_airport = df_flights.groupby("origin").agg(avg_delay=("dep_delay_final", "mean")).reset_index()
        fig_delay_airport = px.bar(df_delay_airport, x="origin", y="avg_delay",
                                   title="Average Departure Delay by Origin Airport",
                                   labels={"origin": "Origin Airport", "avg_delay": "Avg Dep Delay (min)"})
        st.plotly_chart(fig_delay_airport)

    # ---------------------------
    # General Maps Tab
    # ---------------------------
    elif tab == "General Maps":
        st.header("General Maps")
        st.subheader("World Airport Map")
        st.plotly_chart(visuals["fig_world"])
        st.subheader("US Airport Map")
        st.plotly_chart(visuals["fig_us"])

    # ---------------------------
    # Flight Routes Tab
    # ---------------------------
    elif tab == "Flight Routes":
        st.header("Flight Routes")
        selected_airports = st.multiselect("Select destination airports (FAA codes)",  sorted(df_flights["dest"].unique()), key="route_plan")
        if st.button("Plot Routes", key="plot_routes"):
            fig = go.Figure()
            if selected_airports:
                us_only = use_us_scope(selected_airports, df_airports)
                geo_scope = "usa" if us_only else None
                fig.update_layout(geo=dict(scope=geo_scope))
                # Using JFK as the base
                for code in selected_airports:
                    dest = df_airports[df_airports["faa"] == code]
                    origin_code = df_flights[df_flights["dest"] == code]["origin"].iloc[0]
                    origin = df_airports[df_airports["faa"] == origin_code].iloc[0]
                    if not dest.empty:
                        dest = dest.iloc[0]
                        fig.add_trace(
                            go.Scattergeo(
                                locationmode="USA-states" if us_only else None,
                                lon=[origin["lon"], dest["lon"]],
                                lat=[origin["lat"], dest["lat"]],
                                mode="lines",
                                line=dict(width=2, color="red"),
                                name=f"{df_airports[df_airports["faa"] == origin_code]["name"].iloc[0]} to {df_airports[df_airports["faa"] == code]["name"].iloc[0]}",
                            )
                        )
            st.plotly_chart(fig)

    # ---------------------------
    # Distance Analysis Tab
    # ---------------------------
    elif tab == "Distance Analysis":
        st.header("Distance Analysis")
        st.subheader("Euclidean Distance Distribution")
        st.plotly_chart(visuals["fig_hist_euc"])
        st.subheader("Geodesic Distance Distribution")
        st.plotly_chart(visuals["fig_hist_geo"])
        st.subheader("Flight Distance vs. Arrival Delay")
        st.plotly_chart(visuals["fig_distance_vs_arr_delay"])

    # ---------------------------
    # Flights by Day Tab
    # ---------------------------
    elif tab == "Flights by Day":
        st.header("Flights by Day")
        col1, col2, col3 = st.columns(3)
        month = col1.number_input("Month (1-12)", min_value=1, max_value=12, value=1)
        day = col2.number_input("Day (1-31)", min_value=1, max_value=31, value=1)
        origin = col3.selectbox("Select Origin Airport", sorted(df_flights["origin"].unique()), key="daily_origin")
        if st.button("Get Daily Stats", key="daily_stats"):
            df_daily = df_flights.copy()
            df_daily["month"] = df_daily["time_hour"].apply(ensure_datetime).dt.month
            df_daily["day"] = df_daily["time_hour"].apply(ensure_datetime).dt.day
            df_filtered = df_daily[
                (df_daily["month"] == month) & (df_daily["day"] == day) & (df_daily["origin"] == origin)
            ]
            if df_filtered.empty:
                st.write("No flights found for the given date and origin.")
            else:
                dest_counts = df_filtered["dest"].value_counts()
                total_flights = len(df_filtered)
                unique_dest = df_filtered["dest"].nunique()
                most_freq_dest = dest_counts.idxmax()
                stats_text = f"Total Flights: {total_flights}, Unique Destinations: {unique_dest}, Most Frequent Destination: {most_freq_dest}"
                st.write(stats_text)
                dest_airports = df_airports[df_airports["faa"].isin(df_filtered["dest"].unique())]
                fig_day = px.scatter_geo(
                    dest_airports,
                    lat="lat",
                    lon="lon",
                    hover_name="name",
                    title=f"Destinations on {month}/{day} from {origin}",
                )
                st.plotly_chart(fig_day)

    # ---------------------------
    # Trajectory Statistics Tab
    # ---------------------------
    elif tab == "Trajectory Statistics":
        st.header("Trajectory Statistics")
        st.subheader("Trajectory Analysis by Plane Type")
        origin_sel = st.selectbox("Select Origin Airport", sorted(df_flights["origin"].unique()), key="traj_origin")
        dest_options = df_flights[df_flights["origin"] == origin_sel]["dest"].unique().tolist()
        dest_sel = st.selectbox("Select Destination Airport", sorted(dest_options), key="traj_dest")
        if st.button("Analyze Trajectory", key="traj_analyze"):
            df_route = df_flights[(df_flights["origin"] == origin_sel) & (df_flights["dest"] == dest_sel)]
            if df_route.empty:
                st.write(f"No flights found from {origin_sel} to {dest_sel}.")
            else:
                df_route = pd.merge(df_route, df_planes[["tailnum", "type"]], on="tailnum", how="left")
                counts = df_route["type"].value_counts().to_dict()
                st.write("Plane Type Counts for this Trajectory:")
                st.write(counts)

    # ---------------------------
    # Manufacturer & Airline Statistics Tab
    # ---------------------------
    elif tab == "Manufacturer & Airline Statistics":
        st.header("Manufacturer & Airline Statistics")
        st.subheader("Average Departure Delay by Airline")
        st.plotly_chart(visuals["fig_airline_delay"])
        st.subheader("Top 5 Manufacturers for a Destination")
        dest_input = st.selectbox("select Destination ", sorted(df_flights["dest"].unique()), key="manuf_input")
        if st.button("Get Manufacturer Stats", key="manuf_button"):
            query = """
                SELECT p.manufacturer, COUNT(*) AS count
                FROM flights f
                JOIN planes p ON f.tailnum = p.tailnum
                WHERE f.dest = ?
                GROUP BY p.manufacturer
                ORDER BY count DESC
                LIMIT 5;
            """
            new_conn = sqlite3.connect("preprocessed_flights.db")
            df_manuf = pd.read_sql_query(query, new_conn, params=(dest_input,))
            new_conn.close()
            if df_manuf.empty:
                st.write(f"No data found for destination {dest_input}.")
            else:
                st.write(df_manuf)

    # ---------------------------
    # Plane Type Analysis Tab
    # ---------------------------
    elif tab == "Plane Type Analysis":
        st.header("Plane Type Analysis")
        st.subheader("Flight Distance vs. Arrival Delay (All Planes)")
        st.plotly_chart(visuals["fig_distance_vs_arr_delay"])
        # Dropdown for selecting a plane type
        plane_types = list(visuals["wind_vs_delay_by_type"].keys())
        selected_pt = st.selectbox("Select Plane Type for Detailed Analysis", plane_types)
        st.subheader(f"Wind Speed vs. Departure Delay for {selected_pt}")
        st.plotly_chart(visuals["wind_vs_delay_by_type"][selected_pt])
        st.subheader(f"Precipitation vs. Departure Delay for {selected_pt}")
        st.plotly_chart(visuals["precip_vs_delay_by_type"][selected_pt])
        st.subheader(f"Average Departure Delay by Airport & Flight Speed for {selected_pt}")
        st.plotly_chart(visuals["delay_airport_speed_by_type"][selected_pt])

@st.cache_data
def load_preprocessed_data(preprocessed_db):
    conn = sqlite3.connect(preprocessed_db)
    df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
    df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
    df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
    df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
    df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)
    return df_airports, df_flights, df_planes, df_weather, df_airlines



# ============================================================================ 
# Main Execution 
# ============================================================================ 
if __name__ == "__main__":
    conn, df_airports, df_flights, df_planes, df_weather, df_airlines = load_data()
    preprocessed_db = "preprocessed_flights.db"
    if os.path.exists(preprocessed_db):
        st.write("Loading preprocessed data from", preprocessed_db)
        conn_preprocessed = sqlite3.connect(preprocessed_db)
        df_airports, df_flights, df_planes, df_weather, df_airlines = load_preprocessed_data(preprocessed_db)
    else:
        df_airports, df_flights, df_planes, df_weather, df_airlines = preprocess_data(
            conn, df_airports, df_flights, df_planes, df_weather, df_airlines
        )
        save_preprocessed_data(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
        conn_preprocessed = sqlite3.connect(preprocessed_db)

    # Precompute and cache all visualizations once
    visuals = create_visualizations(df_airports, df_flights, df_planes, df_weather, df_airlines, preprocessed_db)
    
    run_dashboard(df_airports, df_flights, df_planes, df_weather, df_airlines, conn_preprocessed, visuals)