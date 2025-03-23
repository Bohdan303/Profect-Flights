import streamlit as st
import pandas as pd

def render(df_airports, df_flights, df_planes):
    st.header("Trajectory Statistics")
    origin_sel = st.selectbox("Select Origin Airport", sorted(df_flights["origin"].unique()))
    dest_options = df_flights[df_flights["origin"] == origin_sel]["dest"].unique().tolist()
    dest_sel = st.selectbox("Select Destination Airport", sorted(dest_options))
    if st.button("Analyze Trajectory"):
        df_route = df_flights[(df_flights["origin"] == origin_sel) & (df_flights["dest"] == dest_sel)]
        if df_route.empty:
            st.write(f"No flights found from {origin_sel} to {dest_sel}.")
        else:
            df_route = pd.merge(df_route, df_planes[["tailnum", "type"]], on="tailnum", how="left")
            counts = df_route["type"].value_counts().to_dict()
            st.write("Plane Type Counts for this Trajectory:")
            st.write(counts)
