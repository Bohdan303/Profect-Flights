# main.py
import os

from data_processing.orchestration import create_processed_data_file, preprocess_data
from data_processing.utils.db_utils import load_data, save_processed_data


def create_processed_flights():
    create_processed_data_file()
    
    df_airports, df_flights, df_planes, df_weather, df_airlines = load_data()
    df_airports, df_flights, df_planes, df_weather, df_airlines = preprocess_data(df_airports, df_flights, df_planes, df_weather, df_airlines)

    save_processed_data(df_airports, df_flights, df_planes, df_weather, df_airlines)

def main():
    processed_db = "processed_flights.db"
    # Run preprocessing if preprocessed database does not exist
    if not os.path.exists("processed_flights.db"):
        print("Preprocessed database not found. Running preprocessing...")
        create_processed_flights()
    # Launch the Streamlit dashboard (dashboard/app.py is designed to run as the app)
    from dashboard import app
    app.run_dashboard()

if __name__ == "__main__":
    main()