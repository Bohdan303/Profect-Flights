import pandas as pd

def vectorized_ensure_datetime(series):
    """Converts a Series of time values to UTC-aware datetimes."""
    return pd.to_datetime(series, errors="coerce", utc=True)

def vectorized_clock_to_datetime(series, base_dates):
    s = series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    hours = s.str[:2].astype(int)
    minutes = s.str[2:].astype(int)
    base_dt = pd.to_datetime(base_dates)
    dt = base_dt + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")
    invalid = (hours > 23) | (minutes > 59)
    if invalid.any():
        dt_invalid = pd.to_datetime(base_dates[invalid]) + pd.DateOffset(days=1) + pd.to_timedelta(minutes[invalid], unit="m")
        dt.loc[invalid] = dt_invalid
    return dt

def compute_sched_datetimes(df):
    df["time_hour"] = vectorized_ensure_datetime(df["time_hour"])
    df["base_date"] = df["time_hour"].dt.floor("D")
    df["sched_dep_dt"] = vectorized_clock_to_datetime(df["sched_dep_time"], df["base_date"])
    df["sched_arr_dt"] = vectorized_clock_to_datetime(df["sched_arr_time"], df["base_date"])
    overnight_mask = df["sched_arr_dt"] < df["sched_dep_dt"]
    df.loc[overnight_mask, "sched_arr_dt"] += pd.Timedelta(days=1)
    df["computed_sched_air_time"] = (df["sched_arr_dt"] - df["sched_dep_dt"]).dt.total_seconds() / 60.0
    return df
