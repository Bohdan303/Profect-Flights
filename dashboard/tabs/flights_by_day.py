import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from data_processing.utils.time_utils import ensure_datetime

def render(df_airports, df_flights):
    st.header("Flights by Day")
    col1, col2, col3 = st.columns(3)
    month = col1.number_input("Month (1-12)", min_value=1, max_value=12, value=1)
    day = col2.number_input("Day (1-31)", min_value=1, max_value=31, value=1)
    origin = col3.selectbox("Select Origin Airport", sorted(df_flights["origin"].unique()))
    if st.button("Get Daily Stats"):
        df_daily = df_flights.copy()
        df_daily["time_hour"] = df_daily["time_hour"].apply(ensure_datetime)
        df_daily["month"] = df_daily["time_hour"].dt.month
        df_daily["day"] = df_daily["time_hour"].dt.day
        df_filtered = df_daily[(df_daily["month"] == month) & (df_daily["day"] == day) & (df_daily["origin"] == origin)]
        if df_filtered.empty:
            st.write("No flights found for the given date and origin.")
        else:
            dest_counts = df_filtered["dest"].value_counts()
            total_flights = len(df_filtered)
            unique_dest = df_filtered["dest"].nunique()
            most_freq_dest = dest_counts.idxmax()
            stats_text = f"Total Flights: {total_flights}, Unique Destinations: {unique_dest}, Most Frequent Destination: {most_freq_dest}"
            st.write(stats_text)
            dest_airports = df_airports[df_airports["faa"].isin(df_filtered["dest"].unique())]
            fig_day = px.scatter_geo(
                dest_airports,
                lat="lat",
                lon="lon",
                hover_name="name",
                title=f"Destinations on {month}/{day} from {origin}"
            )
            st.plotly_chart(fig_day)
            
    st.subheader("Delayed Flights by Destination for a Range of Months")
    col1, col2, col3 = st.columns(3)
    start_month = col1.number_input("Start Month", min_value=1, max_value=12, value=1, key="start_month_delayed")
    end_month = col2.number_input("End Month", min_value=1, max_value=12, value=12, key="end_month_delayed")
    destination = col3.selectbox("Select Destination for Delay Count", sorted(df_flights["dest"].unique()), key="dest_delay_count")
    if st.button("Get Delayed Flight Count", key="delayed_count_button"):
        query = """
            SELECT COUNT(*) as delayed_count
            FROM flights
            WHERE dest = ?
              AND month BETWEEN ? AND ?
              AND dep_delay_final > 0;
        """
        conn = sqlite3.connect("preprocessed_flights.db")
        params = (destination, start_month, end_month)
        df_delayed = pd.read_sql_query(query, conn, params=params)
        count = df_delayed["delayed_count"].iloc[0]
        st.write(f"Number of delayed flights to {destination} between months {start_month} and {end_month}: {count}")
