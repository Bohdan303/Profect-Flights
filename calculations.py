import numpy as np
from math import radians, sin, cos, sqrt, atan2
from sklearn.cluster import KMeans

R = 6371  # Earth's radius in km

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
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def euclidean_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Euclidean distance (as a rough approximation) between two points.
    
    Parameters:
        lat1, lon1: Latitude and longitude of the first point.
        lat2, lon2: Latitude and longitude of the second point.
        
    Returns:
        float: Euclidean distance.
    """
    return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def calculate_all(df):
    """
    Calculate all required metrics and add them as new columns to the DataFrame:
      - Euclidean distance from JFK
      - Geodesic distance from JFK
      - Estimated flight time (based on average speed)
      - Cluster assignment using KMeans
    
    Parameters:
        df (pd.DataFrame): DataFrame containing airports data.
        
    Returns:
        pd.DataFrame: Updated DataFrame with new columns.
    """
    # Get JFK's data
    jfk = df[df['FAA'] == "JFK"].iloc[0]
    jfk_lat = jfk['lat']
    jfk_lon = jfk['lon']
    
    # Euclidean distance
    df['euclidean_distance'] = df.apply(
        lambda row: euclidean_distance(jfk_lat, jfk_lon, row['lat'], row['lon']),
        axis=1
    )
    
    # Geodesic (Haversine) distance
    df['geodesic_distance'] = df.apply(
        lambda row: haversine_distance(jfk_lat, jfk_lon, row['lat'], row['lon']),
        axis=1
    )
    
    # KMeans clustering (using lat, lon)
    coordinates = df[['lat', 'lon']]
    kmeans = KMeans(n_clusters=10, random_state=42)
    df['cluster'] = kmeans.fit_predict(coordinates)
    
    # Estimated flight time in hours (using an average flight speed of 900 km/h)
    flight_speed = 900
    df['estimated_flight_time'] = df['geodesic_distance'] / flight_speed
    
    return df
