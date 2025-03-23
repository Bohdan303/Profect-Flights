import pandas as pd
from data_processing.utils.time_utils import ensure_datetime
from data_processing.preprocessing.departure_arrival import process_all_time_fields_vectorized

def compute_local_arrival(df, df_airports):
    """Computes local arrival time using timezone offsets from the airports table.
    Here, we use the processed actual arrival datetime (arr_dt) and add the airport's offset.
    """
    tz_mapping = df_airports.set_index("faa")["tz"].to_dict()
    df["dest_offset"] = df["dest"].map(tz_mapping).fillna(0)
    df["local_arrival"] = df["arr_dt"] + pd.to_timedelta(df["dest_offset"], unit="h")
    df.drop(columns=["dest_offset"], inplace=True)
    return df

def change_sched_time_to_datetime(df):
    df["time_hour"] = df["time_hour"].apply(lambda x: x if isinstance(x, (pd.Timestamp,)) 
                                              else pd.Timestamp(x))
    def combine_time(row, col):
        base_date = row["time_hour"].date()
        try:
            time_val = int(row[col])
        except Exception:
            return None
        time_str = f"{time_val:04d}"
        hour = int(time_str[:2])
        minute = int(time_str[2:])
        return pd.Timestamp.combine(pd.Timestamp(base_date), pd.Timestamp(f"{hour}:{minute}").time())
    df["sched_dep_time"] = df.apply(lambda row: combine_time(row, "sched_dep_time"), axis=1)
    df["sched_arr_time"] = df.apply(lambda row: combine_time(row, "sched_arr_time"), axis=1)
    def adjust_arrival(row):
        dep = row["sched_dep_time"]
        arr = row["sched_arr_time"]
        if dep and arr and arr < dep:
            return arr + pd.Timedelta(days=1)
        return arr
    df["sched_arr_time"] = df.apply(adjust_arrival, axis=1)
    if "dep_delay" in df.columns and "dep_time" in df.columns:
        df["dep_time"] = df["sched_dep_time"] + pd.to_timedelta(df["dep_delay"], unit="m")
    if "arr_delay" in df.columns and "arr_time" in df.columns:
        df["arr_time"] = df["sched_arr_time"] + pd.to_timedelta(df["arr_delay"], unit="m")
    return df

def compute_flight_distances(df, df_airports):
    origin_coords = df_airports[["faa", "lat", "lon"]].rename(columns={"faa": "origin", "lat": "origin_lat", "lon": "origin_lon"})
    dest_coords = df_airports[["faa", "lat", "lon"]].rename(columns={"faa": "dest", "lat": "dest_lat", "lon": "dest_lon"})
    df = df.merge(origin_coords, on="origin", how="left")
    df = df.merge(dest_coords, on="dest", how="left")
    df["euclidean_distance"] = ((df["dest_lat"] - df["origin_lat"])**2 + (df["dest_lon"] - df["origin_lon"])**2)**0.5
    from math import radians, sin, cos, atan2, degrees, sqrt
    def haversine_distance(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return 6371 * c
    df["geodesic_distance"] = df.apply(lambda row: haversine_distance(row["origin_lat"], row["origin_lon"], row["dest_lat"], row["dest_lon"]), axis=1)
    def compute_flight_bearing(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        y = sin(dlon) * cos(lat2)
        x = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
        return (degrees(atan2(y, x)) + 360) % 360
    df["bearing"] = df.apply(lambda row: compute_flight_bearing(row["origin_lat"], row["origin_lon"], row["dest_lat"], row["dest_lon"]), axis=1)
    df.drop(columns=["origin_lat", "origin_lon", "dest_lat", "dest_lon"], inplace=True)
    return df

def preprocess_flights(df, df_airports):
    df.drop_duplicates(inplace=True)
    if "time_hour" in df.columns:
        df["time_hour"] = df["time_hour"].apply(ensure_datetime)
    df = process_all_time_fields_vectorized(df, tol_percent=10)
    df = change_sched_time_to_datetime(df)
    df = compute_flight_distances(df, df_airports)
    df = compute_local_arrival(df, df_airports)
    return df
