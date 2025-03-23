import numpy as np
import pandas as pd
from data_processing.preprocessing.schedule_processing import vectorized_clock_to_datetime

def process_departure_times(df, tol_percent=10):
    dep_time_mask = df["dep_time"].notnull()
    df.loc[dep_time_mask, "dep_dt"] = vectorized_clock_to_datetime(df.loc[dep_time_mask, "dep_time"], df.loc[dep_time_mask, "base_date"])
    missing_dep_time = ~dep_time_mask
    df.loc[missing_dep_time, "dep_dt"] = df.loc[missing_dep_time, "sched_dep_dt"] + pd.to_timedelta(df.loc[missing_dep_time, "dep_delay"].fillna(0), unit="m")
    overnight_mask = df["dep_dt"] < (df["time_hour"] - pd.to_timedelta(1, unit="h"))
    df.loc[overnight_mask, "dep_dt"] += pd.to_timedelta(1, unit="d")
    df["computed_dep_delay"] = (df["dep_dt"] - df["sched_dep_dt"]).dt.total_seconds() / 60.0
    df["dep_delay_final"] = np.where(df["dep_delay"].isnull(), df["computed_dep_delay"], df["dep_delay"])
    diff = abs(df["computed_dep_delay"] - df["dep_delay_final"])
    relative_diff = np.where(abs(df["computed_dep_delay"]) > 0, diff / abs(df["computed_dep_delay"]) * 100, 0)
    adjust_mask = relative_diff > tol_percent
    df.loc[adjust_mask, "dep_delay_final"] = df.loc[adjust_mask, "computed_dep_delay"]
    return df

def process_arrival_times(df, tol_percent=10):
    arr_time_mask = df["arr_time"].notnull()
    df.loc[arr_time_mask, "arr_dt"] = vectorized_clock_to_datetime(df.loc[arr_time_mask, "arr_time"], df.loc[arr_time_mask, "base_date"])
    missing_arr_time = ~arr_time_mask
    df.loc[missing_arr_time, "arr_dt"] = df.loc[missing_arr_time, "sched_arr_dt"] + pd.to_timedelta(df.loc[missing_arr_time, "arr_delay"].fillna(0), unit="m")
    overnight_mask = df["arr_dt"] < (df["time_hour"] - pd.to_timedelta(1, unit="h") + pd.to_timedelta(df["computed_sched_air_time"], unit="m"))
    df.loc[overnight_mask, "arr_dt"] += pd.to_timedelta(1, unit="d")
    df["computed_arr_delay"] = (df["arr_dt"] - df["sched_arr_dt"]).dt.total_seconds() / 60.0
    df["arr_delay_final"] = np.where(df["arr_delay"].isnull(), df["computed_arr_delay"], df["arr_delay"])
    diff = abs(df["computed_arr_delay"] - df["arr_delay_final"])
    relative_diff = np.where(abs(df["computed_arr_delay"]) > 0, diff / abs(df["computed_arr_delay"]) * 100, 0)
    adjust_mask = relative_diff > tol_percent
    df.loc[adjust_mask, "arr_delay_final"] = df.loc[adjust_mask, "computed_arr_delay"]
    return df

def adjust_actual_overnight(df):
    mask = df["arr_dt"] < df["dep_dt"]
    df.loc[mask, "arr_dt"] += pd.Timedelta(days=1)
    return df

def compute_air_time(df, tol_percent=10):
    df["computed_air_time"] = (df["arr_dt"] - df["dep_dt"]).dt.total_seconds() / 60.0
    df["air_time_final"] = np.where(df["air_time"].isnull(), df["computed_air_time"], df["air_time"])
    diff = abs(df["computed_air_time"] - df["air_time_final"])
    relative_diff = np.where(abs(df["computed_air_time"]) > 0, diff / abs(df["computed_air_time"]) * 100, 0)
    adjust_mask = relative_diff > tol_percent
    df.loc[adjust_mask, "air_time_final"] = df.loc[adjust_mask, "computed_air_time"]
    return df

def process_all_time_fields_vectorized(df, tol_percent=10):
    from data_processing.preprocessing.schedule_processing import compute_sched_datetimes
    df = compute_sched_datetimes(df)
    df = process_departure_times(df, tol_percent)
    df = process_arrival_times(df, tol_percent)
    df = adjust_actual_overnight(df)
    df = compute_air_time(df, tol_percent)
    return df
