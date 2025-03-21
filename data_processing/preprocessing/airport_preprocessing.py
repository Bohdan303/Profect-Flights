import pandas as pd
import numpy as np
from timezonefinder import TimezoneFinder
import pytz
import reverse_geocoder as rg
import pycountry
import pycountry_convert as pc

tf = TimezoneFinder()

def augment_airports_with_missing(df_airports, df_flights):
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
        print("airportsdata module not available. Install it with 'pip install airportsdata'")
        return df_airports
    new_rows = []
    for code in missing_codes:
        if code in airports_dict:
            info = airports_dict[code]
            new_rows.append({
                "faa": code,
                "name": info.get("name", ""),
                "lat": info.get("lat", None),
                "lon": info.get("lon", None),
                "alt": info.get("elevation", None),
                "tz": np.nan,
                "dst": np.nan,
                "tzone": np.nan,
            })
        else:
            print(f"No external data found for missing airport code: {code}")
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_airports = pd.concat([df_airports, df_new], ignore_index=True)
        print("Augmented airports table with missing data for codes:", sorted(missing_codes))
    return df_airports

def compute_timezone_info_for_missing(df_airports):
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
            tz, tz_offset, dst_active = None, None, None
        return pd.Series([tz_offset, dst_active, tz], index=["tz", "dst", "tzone"])

    missing_mask = df_airports[["tz", "dst", "tzone"]].isna().any(axis=1)
    df_airports.loc[missing_mask, ["tz", "dst", "tzone"]] = df_airports.loc[missing_mask].apply(compute_info_for_row, axis=1)
    return df_airports

def country_to_continent(country_code):
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
    df_airports = augment_airports_with_missing(df_airports, df_flights)
    df_airports = compute_timezone_info_for_missing(df_airports)
    df_airports = add_location_info_to_airports(df_airports)
    return df_airports
