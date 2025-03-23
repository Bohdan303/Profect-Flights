import pandas as pd
import time
import requests
from data_processing.utils.time_utils import convert_time_hour_to_utc, ensure_datetime
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
HOURLY_PARAMS = (
    "temperature_2m,dewpoint_2m,relativehumidity_2m,"
    "winddirection_10m,windspeed_10m,windgusts_10m,"
    "precipitation,surface_pressure,visibility"
)

def merge_airport_data(df_weather, df_airports):
    df_airports_subset = df_airports[["faa", "lat", "lon", "tz"]]
    return df_weather.merge(df_airports_subset, left_on="origin", right_on="faa", how="left", suffixes=("", "_airport"))

def convert_time_columns(df_weather):
    df_weather["dt"] = df_weather["time_hour"].apply(convert_time_hour_to_utc)
    return df_weather

def get_weather_data_with_backoff(params, max_retries=5):
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
    df_weather = merge_airport_data(df_weather, df_airports)
    df_weather = convert_time_columns(df_weather)
    missing_mask = df_weather["temp"].isnull()
    missing_df = df_weather[missing_mask].copy()
    unique_origins = missing_df["origin"].unique()
    if len(unique_origins) <= 4:
        updated_subsets = []
        with ThreadPoolExecutor(max_workers=len(unique_origins)) as executor:
            futures = {executor.submit(process_origin_weather, origin, df_weather, df_airports): origin for origin in unique_origins}
            for future in futures:
                try:
                    updated_subsets.append(future.result())
                except Exception as e:
                    print(f"Error processing origin {futures[future]}: {e}")
        for subset in updated_subsets:
            if not subset.empty:
                df_weather.loc[subset.index, :] = subset
    else:
        # If more origins, process in chunks
        chunks = np.array_split(missing_df, 4)
        updated_chunks = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_origin_weather, chunk["origin"].iloc[0], df_weather, df_airports): i for i, chunk in enumerate(chunks)}
            for future in futures:
                try:
                    updated_chunks.append(future.result())
                except Exception as e:
                    print(f"Error processing chunk: {e}")
        for chunk in updated_chunks:
            if not chunk.empty:
                df_weather.loc[chunk.index, :] = chunk
    df_weather.drop(columns=["faa"], inplace=True, errors="ignore")
    return df_weather

def analyze_weather_effects(df_flights, df_weather):
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
