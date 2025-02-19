import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import seaborn as sns
from math import radians, sin, cos, sqrt, atan2
from plotly.colors import sample_colorscale
from timezonefinder import TimezoneFinder
import pytz
from sklearn.cluster import KMeans
import numpy as np

# Load the dataset
df_airports = pd.read_csv("airports.csv", delimiter=",")
df_airports.columns = ["FAA", "name", "lat", "lon", "alt", "tz", "dst", "tzone"]

# Create a TimezoneFinder object
tf = TimezoneFinder()

# Function to get timezone data only if missing
def get_timezone_data(row):
    try:
        if pd.isna(row['tz']) or pd.isna(row['dst']) or pd.isna(row['tzone']):  # Check if any value is missing
            timezone = tf.timezone_at(lng=row['lon'], lat=row['lat'])  # Get timezone name
            if timezone:
                tz_obj = pytz.timezone(timezone)

                # Get UTC offset (tz) and DST status
                now = pd.Timestamp.now(tz=pytz.utc)
                local_now = now.astimezone(tz_obj)

                tz_offset = local_now.utcoffset().total_seconds() / 3600  # Convert seconds to hours
                dst_active = "A" if local_now.dst() != pd.Timedelta(0) else "N"  # 'A' for active, 'N' for not active

                return pd.Series([tz_offset, dst_active, timezone], index=['tz', 'dst', 'tzone'])  # Ensure correct index
    except:
        pass  # Keep original values if an error occurs
    
    return pd.Series([row['tz'], row['dst'], row['tzone']], index=['tz', 'dst', 'tzone'])  # Ensure correct shape

# Apply function only to missing values
df_airports[['tz', 'dst', 'tzone']] = df_airports.apply(get_timezone_data, axis=1)

# Remove rows with any missing values
df_airports = df_airports.dropna()

# Time zone distribution
timezone_counts = df_airports['tz'].value_counts()

# --- Calculations ---
# Euclidean distance calculation
def euclidean_distance(row):
    jfk = df_airports[df_airports['FAA'] == "JFK"].iloc[0]
    return np.sqrt((jfk['lat'] - row['lat'])**2 + (jfk['lon'] - row['lon'])**2)

df_airports['euclidean_distance'] = df_airports.apply(euclidean_distance, axis=1)

# Haversine distance calculation
R = 6371  # Earth's radius in km
def haversine_distance(row):
    jfk = df_airports[df_airports['FAA'] == "JFK"].iloc[0]
    lat1, lon1 = radians(jfk['lat']), radians(jfk['lon'])
    lat2, lon2 = radians(row['lat']), radians(row['lon'])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(np.clip(a, 0, 1)), sqrt(np.clip(1 - a, 0, 1)))
    return R * c

df_airports['geodesic_distance'] = df_airports.apply(haversine_distance, axis=1)

# KMeans clustering for airport proximity
coordinates = df_airports[['lat', 'lon']]
kmeans = KMeans(n_clusters=10, random_state=42)
df_airports['cluster'] = kmeans.fit_predict(coordinates)

# Estimated flight time (in hours) calculation
def estimate_flight_time(row):
    flight_speed = 900  # Average commercial flight speed in km/h
    return row['geodesic_distance'] / flight_speed

df_airports['estimated_flight_time'] = df_airports.apply(estimate_flight_time, axis=1)

# --- New Analysis: Flight Time Prediction ---

# Function to estimate flight time from JFK (in hours)
def estimate_flight_time(row):
    flight_speed = 900  # Average commercial flight speed in km/h
    return row['geodesic_distance'] / flight_speed

df_airports['estimated_flight_time'] = df_airports.apply(estimate_flight_time, axis=1)

# Filter US airports
df_us_airports = df_airports[df_airports['tzone'].str.contains("America", na=False)]

# --- Visualization of Flight Times ---

# 1. Scatter plot of Estimated Flight Time vs Airport Altitude
plt.figure(figsize=(10, 6))
plt.scatter(df_airports['alt'], df_airports['estimated_flight_time'], color='green', alpha=0.5)
plt.xlabel('Airport Altitude (m)')
plt.ylabel('Estimated Flight Time (hours)')
plt.title('Estimated Flight Time vs Airport Altitude')
plt.show()

# --- New Analysis: Distance vs Altitude ---

# Scatter plot of Distance (geodesic) vs Altitude
plt.figure(figsize=(10, 6))
plt.scatter(df_airports['geodesic_distance'], df_airports['alt'], color='red', alpha=0.5)
plt.xlabel('Geodesic Distance from JFK (km)')
plt.ylabel('Airport Altitude (m)')
plt.title('Geodesic Distance vs Airport Altitude')
plt.show()


# --- Scatter Plots ---
# 1. Scatter plot for all airports (World)
fig_world = px.scatter_geo(df_airports, lat='lat', lon='lon', hover_name='name', title="Airport Locations Worldwide")
fig_world.show()

# 2. Scatter plot for US airports
fig_us = px.scatter_geo(df_us_airports, lat='lat', lon='lon', hover_name='name', title="US Airports")
fig_us.show()

# 3. Scatter plot for altitude
fig_alt = px.scatter_geo(df_airports, lat='lat', lon='lon', hover_name='name', color='alt', title="Airports by Altitude", color_continuous_scale="viridis")
fig_alt.show()

# 4. Scatter plot for geodesic distance from JFK
fig_geo_dist = px.scatter_geo(df_airports, lat='lat', lon='lon', color='geodesic_distance', hover_name='name', color_continuous_scale='Viridis', title="airports heatmap by geodesic distance from JFK")
fig_geo_dist.update_geos(showcoastlines=True, coastlinecolor="Black")
fig_geo_dist.show()

# 5. Scatter plot for Euclidean distance from JFK
fig_euclidean_dist = px.scatter_geo(df_airports, lat='lat', lon='lon', color='euclidean_distance', hover_name='name', color_continuous_scale='Viridis', title="airports heatmap by euclidean distance from JFK")
fig_euclidean_dist.update_geos(showcoastlines=True, coastlinecolor="Black")
fig_euclidean_dist.show()

# 6. Scatter plot for time zone
fig_tz = px.scatter_geo(df_airports, lat='lat', lon='lon', hover_name='name', color='tz', title="Airports by Time Zone", color_continuous_scale="viridis")
fig_tz.show()

# clusters of airport locations around JFK us
fig_geo_dist = px.scatter_geo(df_us_airports, lat='lat', lon='lon', color='cluster', hover_name='name', color_continuous_scale='Viridis', title="Airport Clusters Around JFK in the US")
fig_geo_dist.update_geos(showcoastlines=True, coastlinecolor="Black")
fig_geo_dist.show()

#---Route Plotting---
df_airports['geodesic_distance'] = df_airports.apply(haversine_distance, axis=1)

# Compute global min and max distances for normalization
min_distance = df_airports['geodesic_distance'].min()
max_distance = df_airports['geodesic_distance'].max()

# Filter and prepare data for US airports
df_us_airports = df_airports[df_airports['tzone'].str.contains("America", na=False)]

# Function to plot multiple routes from JFK
# This function plots multiple routes from JFK to several airports with color-coding based on distance
def plot_routes(airport_codes):
    nyc = df_airports[df_airports['FAA'] == "JFK"]
    
    if nyc.empty:
        print("JFK airport not found.")
        return
    
    fig = go.Figure()
    
    for code in airport_codes:
        target_airport = df_airports[df_airports['FAA'] == code]

        # Compute the distance (using your haversine_distance function)
        distance = haversine_distance(target_airport.iloc[0])
    
        # Normalize the distance
        norm_value = (distance - min_distance) / (max_distance - min_distance)
    
        # Get a color from the 'Viridis' colorscale
        color = sample_colorscale('Viridis', [norm_value])[0]
        
        if not target_airport.empty:
            fig.add_trace(go.Scattergeo(
                lat=[nyc['lat'].values[0], target_airport['lat'].values[0]],
                lon=[nyc['lon'].values[0], target_airport['lon'].values[0]],
                mode='lines+markers',
                line=dict(width=2, color=color),
                marker=dict(size=8, symbol="circle"),
                text=f"{code} ({distance:.2f} km)", 
                textsrc="JFK", 
                name=f"JFK → {code}({distance:.2f} km)"
            ))
        else:
            print(f"Invalid airport code: {code}")
    
    fig.update_layout(title="Flight Routes from JFK", geo=dict(showland=True, landcolor="lightgray"))
    fig.show()

user_input = input("Enter FAA codes seperated by commas with no spaces (FAA,FAA,FAA):")
input_FAA_codes = [code.strip().upper() for code in user_input.split(",") if code.strip()]

plot_routes(input_FAA_codes)

# --- Bar Charts ---
# 1. Distribution of airports by time zone
plt.figure(figsize=(12, 6))
sns.barplot(x=timezone_counts.index, y=timezone_counts.values, palette="coolwarm")
plt.xticks(rotation=45)
plt.xlabel("Time Zones")
plt.ylabel("Number of Airports")
plt.title("Time Zones Distribution of Airports")
plt.show()

# 2. Histogram for Euclidean distances
plt.hist(df_airports['euclidean_distance'], bins=50, color='blue')
plt.xlabel("Euclidean Distance from JFK")
plt.ylabel("Number of Airports")
plt.title("Distribution of Euclidean Distances from JFK")
plt.show()

# 3. Histogram for Geodesic distances
plt.hist(df_airports['geodesic_distance'], bins=50, color='orange')
plt.xlabel("Geodesic Distance from JFK (km)")
plt.ylabel("Number of Airports")
plt.title("Distribution of Geodesic Distances from JFK")
plt.show()

# 4. Histogram for Estimated Flight Times
plt.figure(figsize=(10, 6))
plt.hist(df_airports['estimated_flight_time'], bins=50, color='purple', edgecolor='black')
plt.xlabel('Estimated Flight Time (hours)')
plt.ylabel('Number of Airports')
plt.title('Distribution of Estimated Flight Times from JFK')
plt.show()

# --- Pie Chart ---
# 1. Time Zones Distribution (Pie chart)
plt.figure(figsize=(8, 8))
plt.pie(timezone_counts, labels=timezone_counts.index, autopct='%1.1f%%', colors=sns.color_palette("coolwarm", len(timezone_counts)), startangle=90)
plt.title("Time Zones Distribution of Airports")
plt.axis('equal')
plt.show()

# Plot time zones distribution as a pie chart with percentages outside and lines pointing to each wedge
plt.figure(figsize=(10, 8))
wedges, texts, autotexts = plt.pie(timezone_counts, labels=timezone_counts.index, autopct='%1.1f%%', 
                                   colors=sns.color_palette("coolwarm", len(timezone_counts)), startangle=90,
                                   wedgeprops={'edgecolor': 'black', 'linewidth': 1.5},
                                   pctdistance=1.1, labeldistance=100)

# Customize the text properties for the labels and percentages
for text in texts:
    text.set_fontsize(12)
    text.set_fontweight('bold')

for autotext in autotexts:
    autotext.set_fontsize(12)
    autotext.set_fontweight('bold')

# Add a legend to the chart
plt.legend(wedges, timezone_counts.index, title="Time Zones", loc="upper left", bbox_to_anchor=(1, 1))

plt.title("Time Zones Distribution of Airports")
plt.axis('equal')  # Equal aspect ratio ensures that pie chart is drawn as a circle.
plt.show()