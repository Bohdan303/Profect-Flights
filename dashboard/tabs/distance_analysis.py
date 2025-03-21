import streamlit as st

def render(df_flights, visuals):
    st.header("Distance Analysis")
    st.subheader("Geodesic Distance Histogram")
    st.plotly_chart(visuals.get("fig_distance_hist"))
    st.subheader("Delay vs. Distance")
    st.plotly_chart(visuals.get("fig_delay_vs_distance"))
