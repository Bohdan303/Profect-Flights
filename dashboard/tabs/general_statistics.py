import streamlit as st
import pandas as pd
import plotly.express as px

def render(df_airports, df_flights, visuals):
    st.header("General Statistics")
    # Merge flight and airport info to get timezone details
    df_tz = pd.merge(df_flights, df_airports[["faa", "tz"]], left_on="dest", right_on="faa", how="left")
    tz_counts = df_tz.groupby("tz").agg(avg_dep_delay=("dep_delay_final", "mean")).reset_index()
    fig_tz = px.bar(tz_counts, x="tz", y="avg_dep_delay",
                    title="Average Departure Delay by Destination Time Zone",
                    labels={"tz": "Time Zone", "avg_dep_delay": "Avg Departure Delay (min)"})
    st.plotly_chart(fig_tz)
    # Show world map from visualizations
    st.plotly_chart(visuals.get("fig_world"))
