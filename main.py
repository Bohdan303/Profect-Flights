# main.py

import os
from data_processing import preprocessing

def main():
    preprocessed_db = "preprocessed_flights.db"
    # Run preprocessing if preprocessed database does not exist
    if not os.path.exists(preprocessed_db):
        preprocessing.run_preprocessing()
    # Launch the Streamlit dashboard (dashboard/app.py is designed to run as the app)
    from dashboard import app
    app.run_dashboard()

if __name__ == "__main__":
    main()