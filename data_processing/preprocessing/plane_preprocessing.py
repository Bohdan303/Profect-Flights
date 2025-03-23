import pandas as pd

def infer_manufacture_year(df_planes):
    def fill_missing_with_mode(series):
        non_null = series.dropna()
        if non_null.empty:
            return series
        mode_val = non_null.mode().iloc[0]
        return series.fillna(mode_val)
    df_planes["year"] = df_planes.groupby("model")["year"].transform(fill_missing_with_mode)
    return df_planes

def update_plane_speed(df_flights, df_planes):
    valid = df_flights[df_flights["air_time"] > 0]
    df_speed = valid.groupby("tailnum").apply(lambda x: (60.0 * x["distance"].sum()) / x["air_time"].sum()).reset_index(name="avg_speed")
    df_planes = df_planes.merge(df_speed, on="tailnum", how="left")
    df_planes["speed"] = df_planes.apply(lambda row: row["avg_speed"] if pd.isnull(row["speed"]) or row["speed"] == "" else row["speed"], axis=1)
    df_planes.drop(columns=["avg_speed"], inplace=True)
    return df_planes

def preprocess_planes(df_planes, df_flights):
    df_planes["year"] = pd.to_numeric(df_planes["year"], errors="coerce")
    df_planes = infer_manufacture_year(df_planes)
    df_planes = update_plane_speed(df_flights, df_planes)
    return df_planes
