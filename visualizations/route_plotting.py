import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from calculations import haversine_distance

def plot_routes(df, airport_codes):
    """
    Plot multiple flight routes from JFK to the given airport codes.
    Routes are color-coded based on geodesic distance.
    
    Parameters:
        df (pd.DataFrame): DataFrame with airports data.
        airport_codes (list): List of FAA codes to plot routes for.
    """
    # Get JFK's location
    jfk_row = df[df['FAA'] == "JFK"]
    if jfk_row.empty:
        print("JFK airport not found.")
        return
    jfk_lat = jfk_row.iloc[0]['lat']
    jfk_lon = jfk_row.iloc[0]['lon']
    
    # Compute global min and max geodesic distances (for normalization)
    min_distance = df['geodesic_distance'].min()
    max_distance = df['geodesic_distance'].max()
    
    fig = go.Figure()
    
    for code in airport_codes:
        target = df[df['FAA'] == code]
        if target.empty:
            print(f"Invalid airport code: {code}")
            continue
        target_lat = target.iloc[0]['lat']
        target_lon = target.iloc[0]['lon']
        # Calculate distance using Haversine formula
        distance = haversine_distance(jfk_lat, jfk_lon, target_lat, target_lon)
        # Normalize the distance for colorscale (0 to 1)
        norm_value = (distance - min_distance) / (max_distance - min_distance)
        color = sample_colorscale('Viridis', [norm_value])[0]
        
        fig.add_trace(go.Scattergeo(
            lat=[jfk_lat, target_lat],
            lon=[jfk_lon, target_lon],
            mode='lines+markers',
            line=dict(width=2, color=color),
            marker=dict(size=8, symbol="circle"),
            text=f"{code} ({distance:.2f} km)", 
            textsrc="JFK", 
            name=f"JFK → {code}({distance:.2f} km)"
        ))
    
    fig.update_layout(
        title="Flight Routes from JFK",
        geo=dict(showland=True, landcolor="lightgray")
    )
    fig.show()
