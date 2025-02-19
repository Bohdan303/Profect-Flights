import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns

def plot_world_airports(df):
    """
    Plot world airports using a scatter_geo map.
    """
    fig = px.scatter_geo(df, lat='lat', lon='lon', hover_name='name', 
                          title="Airport Locations Worldwide")
    fig.show()

def plot_us_airports(df_us):
    """
    Plot US airports using a scatter_geo map.
    """
    fig = px.scatter_geo(df_us, lat='lat', lon='lon', hover_name='name', 
                          title="US Airports")
    fig.show()

def plot_altitude_scatter(df):
    """
    Scatter plot: Estimated Flight Time vs Airport Altitude (using matplotlib).
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(df['alt'], df['estimated_flight_time'], color='green', alpha=0.5)
    plt.xlabel('Airport Altitude (m)')
    plt.ylabel('Estimated Flight Time (hours)')
    plt.title('Estimated Flight Time vs Airport Altitude')
    plt.show()

def plot_geodesic_vs_altitude(df):
    """
    Scatter plot: Geodesic Distance from JFK vs Airport Altitude.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(df['geodesic_distance'], df['alt'], color='red', alpha=0.5)
    plt.xlabel('Geodesic Distance from JFK (km)')
    plt.ylabel('Airport Altitude (m)')
    plt.title('Geodesic Distance vs Airport Altitude')
    plt.show()

def plot_distance_heatmaps(df):
    """
    Create scatter_geo heatmaps for geodesic and Euclidean distances from JFK.
    """
    # Geodesic distance heatmap
    fig_geo = px.scatter_geo(df, lat='lat', lon='lon', 
                             color='geodesic_distance', hover_name='name',
                             color_continuous_scale='Viridis',
                             title="Airports Heatmap by Geodesic Distance from JFK")
    fig_geo.update_geos(showcoastlines=True, coastlinecolor="Black")
    fig_geo.show()
    
    # Euclidean distance heatmap
    fig_euclid = px.scatter_geo(df, lat='lat', lon='lon', 
                                color='euclidean_distance', hover_name='name',
                                color_continuous_scale='Viridis',
                                title="Airports Heatmap by Euclidean Distance from JFK")
    fig_euclid.update_geos(showcoastlines=True, coastlinecolor="Black")
    fig_euclid.show()

def plot_timezone_map(df):
    """
    Plot a scatter_geo map with airports colored by their time zone.
    """
    fig = px.scatter_geo(df, lat='lat', lon='lon', hover_name='name', 
                         color='tz', title="Airports by Time Zone",
                         color_continuous_scale="viridis")
    fig.show()
