import streamlit as st
import sqlite3
import pandas as pd

def render(df_airports, df_flights, df_airlines,visuals):
    st.header("Manufacturer & Airline Statistics")
    st.subheader("Average Departure Delay per Airline")
    st.plotly_chart(visuals["fig_airline_delay"])
    st.subheader("Top 5 Manufacturers for a Destination")
    dest_input = st.selectbox("Select Destination", sorted(df_flights["dest"].unique()))
    if st.button("Get Manufacturer Stats"):
        query = """
            SELECT p.manufacturer, COUNT(*) AS count
            FROM flights f
            JOIN planes p ON f.tailnum = p.tailnum
            WHERE f.dest = ?
            GROUP BY p.manufacturer
            ORDER BY count DESC
            LIMIT 5;
        """
        new_conn = sqlite3.connect("preprocessed_flights.db")
        df_manuf = pd.read_sql_query(query, new_conn, params=(dest_input,))
        new_conn.close()
        if df_manuf.empty:
            st.write(f"No data found for destination {dest_input}.")
        else:
            st.write(df_manuf)
