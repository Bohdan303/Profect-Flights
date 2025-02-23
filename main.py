import random
from data_loader import load_data
from calculations.calculations import calculate_all
from calculations.db_queries import run_all_db_functions
from visualizations import route_plotting, scatterplot, barchart, piecharts

def main():
    # --- Data Loading ---
    print("Loading data...")
    df = load_data("airports.csv")
    
    # --- Calculations ---
    print("Calculating distances, flight times, and clusters...")
    df = calculate_all(df)
    
    # Optional: Filter US airports if needed for some plots
    df_us_airports = df[df['tzone'].str.contains("America", na=False)]
    
    # --- Visualizations ---
    
    # Scatter Plots
    print("Generating scatter plots...")
    scatterplot.plot_world_airports(df)
    scatterplot.plot_us_airports(df_us_airports)
    scatterplot.plot_altitude_scatter(df)
    scatterplot.plot_geodesic_vs_altitude(df)
    scatterplot.plot_distance_heatmaps(df)
    scatterplot.plot_timezone_map(df)
    
    # Route Plotting
    print("Plotting flight routes from JFK...")
    # Ask for an input of FAA codes for route plotting
    user_input = input("Enter FAA codes seperated by commas with no spaces (FAA,FAA,FAA):")
    input_FAA_codes = [code.strip().upper() for code in user_input.split(",") if code.strip()]
    route_plotting.plot_routes(df, input_FAA_codes)
    
    
    # Bar Charts / Histograms
    print("Generating bar charts and histograms...")
    barchart.plot_timezone_bar_chart(df)
    barchart.plot_histogram_euclidean(df)
    barchart.plot_histogram_geodesic(df)
    barchart.plot_histogram_flight_time(df)
    
    # Pie Charts
    print("Generating pie charts...")
    piecharts.plot_timezone_pie_chart(df)
    
    #db_queries 
    print("Running database queries...")
    run_all_db_functions()
    
if __name__ == "__main__":
    main()
