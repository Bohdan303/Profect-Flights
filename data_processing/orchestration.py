# data_processing/preprocessing.py
import os
import sqlite3

def run_sql_updates(conn):
    cursor = conn.cursor()
    
    # Add new columns to flights if they don’t already exist.
    new_columns = [
        ("sched_dep_dt", "TEXT"),
        ("sched_arr_dt", "TEXT"),
        ("computed_sched_air_time", "REAL"),
        ("dep_dt", "TEXT"),
        ("computed_dep_delay", "REAL"),
        ("dep_delay_final", "REAL"),
        ("arr_dt", "TEXT"),
        ("computed_arr_delay", "REAL"),
        ("arr_delay_final", "REAL"),
        ("computed_air_time", "REAL"),
        ("air_time_final", "REAL"),
        ("local_arrival", "TEXT")
    ]
    for col, coltype in new_columns:
        try:
            cursor.execute(f"ALTER TABLE flights ADD COLUMN {col} {coltype}")
        except sqlite3.OperationalError:
            pass  # Assume column already exists

    # Compute scheduled departure datetime using time_hour and sched_dep_time.
    cursor.execute("""
    UPDATE flights
    SET sched_dep_dt = datetime(date(time_hour) || ' ' || substr(printf('%04d', sched_dep_time), 1, 2) || ':' || substr(printf('%04d', sched_dep_time), 3, 2))
    WHERE sched_dep_dt IS NULL
    """)
    
    # Compute scheduled arrival datetime similarly.
    cursor.execute("""
    UPDATE flights
    SET sched_arr_dt = datetime(date(time_hour) || ' ' || substr(printf('%04d', sched_arr_time), 1, 2) || ':' || substr(printf('%04d', sched_arr_time), 3, 2))
    WHERE sched_arr_dt IS NULL
    """)
    
    # Adjust overnight scheduled arrival.
    cursor.execute("""
    UPDATE flights
    SET sched_arr_dt = datetime(sched_arr_dt, '+1 day')
    WHERE sched_arr_dt < sched_dep_dt
    """)
    
    # Compute computed scheduled air time in minutes.
    cursor.execute("""
    UPDATE flights
    SET computed_sched_air_time = (julianday(sched_arr_dt) - julianday(sched_dep_dt)) * 24 * 60
    """)
    
    # Compute departure datetime (dep_dt): if dep_time is available use it; otherwise, use sched_dep_dt plus dep_delay minutes.
    cursor.execute("""
    UPDATE flights
    SET dep_dt = CASE 
         WHEN dep_time IS NOT NULL THEN datetime(date(time_hour) || ' ' || substr(printf('%04d', dep_time), 1, 2) || ':' || substr(printf('%04d', dep_time), 3, 2))
         ELSE datetime(sched_dep_dt, '+' || IFNULL(dep_delay,0) || ' minutes')
      END
    """)
    
    # Adjust overnight departure.
    cursor.execute("""
    UPDATE flights
    SET dep_dt = datetime(dep_dt, '+1 day')
    WHERE dep_dt < datetime(time_hour, '-1 hours')
    """)
    
    # Compute computed departure delay in minutes.
    cursor.execute("""
    UPDATE flights
    SET computed_dep_delay = (julianday(dep_dt) - julianday(sched_dep_dt)) * 24 * 60
    """)
    
    # Set departure delay final.
    cursor.execute("""
    UPDATE flights
    SET dep_delay_final = CASE WHEN dep_delay IS NULL THEN computed_dep_delay ELSE dep_delay END
    """)
    
    # Compute arrival datetime (arr_dt): if arr_time is available use it; otherwise, use sched_arr_dt plus arr_delay minutes.
    cursor.execute("""
    UPDATE flights
    SET arr_dt = CASE 
         WHEN arr_time IS NOT NULL THEN datetime(date(time_hour) || ' ' || substr(printf('%04d', arr_time), 1, 2) || ':' || substr(printf('%04d', arr_time), 3, 2))
         ELSE datetime(sched_arr_dt, '+' || IFNULL(arr_delay,0) || ' minutes')
      END
    """)
    
    # Adjust overnight arrival.
    cursor.execute("""
    UPDATE flights
    SET arr_dt = datetime(arr_dt, '+1 day')
    WHERE arr_dt < datetime(time_hour, '-1 hours', '+' || computed_sched_air_time || ' minutes')
    """)
    
    # Compute computed arrival delay in minutes.
    cursor.execute("""
    UPDATE flights
    SET computed_arr_delay = (julianday(arr_dt) - julianday(sched_arr_dt)) * 24 * 60
    """)
    
    # Set arrival delay final.
    cursor.execute("""
    UPDATE flights
    SET arr_delay_final = CASE WHEN arr_delay IS NULL THEN computed_arr_delay ELSE arr_delay END
    """)
    
    # Compute computed air time and set air time final.
    cursor.execute("""
    UPDATE flights
    SET computed_air_time = (julianday(arr_dt) - julianday(dep_dt)) * 24 * 60,
        air_time_final = CASE WHEN air_time IS NULL THEN (julianday(arr_dt) - julianday(dep_dt)) * 24 * 60 ELSE air_time END
    """)
    
    # Compute local arrival using the timezone offset from the airports table.
    cursor.execute("""
    UPDATE flights
    SET local_arrival = datetime(arr_dt, '+' || (
      SELECT tz FROM airports WHERE airports.faa = flights.dest
    ) || ' hours')
    """)
    
    conn.commit()
    cursor.close()

def run_preprocessing():
    raw_db = "flights_database.db"
    preprocessed_db = "preprocessed_flights.db"
    
    if os.path.exists(preprocessed_db):
        os.remove(preprocessed_db)
    
    # Open connection to raw database.
    conn_raw = sqlite3.connect(raw_db)
    
    # Create new preprocessed DB.
    conn_pre = sqlite3.connect(preprocessed_db)
    cursor_pre = conn_pre.cursor()
    
    # Copy tables from raw DB into preprocessed DB.
    tables = ["airports", "flights", "planes", "weather", "airlines"]
    for table in tables:
        # Create table using the raw schema.
        schema = conn_raw.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()[0]
        cursor_pre.execute(schema)
        # Fetch all data from raw table.
        data = conn_raw.execute(f"SELECT * FROM {table}").fetchall()
        if data:
            col_names = [description[0] for description in conn_raw.execute(f"PRAGMA table_info({table})")]
            placeholders = ",".join("?" * len(col_names))
            cursor_pre.executemany(f"INSERT INTO {table} VALUES ({placeholders})", data)
        conn_pre.commit()
    
    cursor_pre.close()
    conn_raw.close()
    
    # Now run the SQL updates to compute the new columns.
    conn = sqlite3.connect(preprocessed_db)
    run_sql_updates(conn)
    conn.close()
    print("Preprocessing complete. Data saved to", preprocessed_db)

if __name__ == "__main__":
    run_preprocessing()