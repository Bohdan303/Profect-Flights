import os
import sqlite3
import pandas as pd

def load_data(db_path="flights_database.db"):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode = MEMORY")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = 100000")

        # Check if the flights table exists
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        table_names = [table[0] for table in tables]

        if "flights" not in table_names:
            error(f"Error: The 'flights' table does not exist in the database '{db_path}'.")
            raise ValueError(f"The 'flights' table is missing in the database '{db_path}'.")

        # Create index if the table exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flights_dest ON flights(dest)")
        conn.commit()

        # Load data into DataFrames
        df_airports = pd.read_sql_query("SELECT * FROM airports", conn)
        df_flights = pd.read_sql_query("SELECT * FROM flights", conn)
        df_planes = pd.read_sql_query("SELECT * FROM planes", conn)
        df_weather = pd.read_sql_query("SELECT * FROM weather", conn)
        df_airlines = pd.read_sql_query("SELECT * FROM airlines", conn)

        return conn, df_airports, df_flights, df_planes, df_weather, df_airlines

    except sqlite3.OperationalError as e:
        error("Database error occurred. Please ensure the database is valid and the required tables exist.")
        error(f"Original error message: {e}")
        raise
    except Exception as e:
        error("An unexpected error occurred.")
        error(f"Original error message: {e}")
        raise
