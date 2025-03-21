import streamlit as st

def render(df_airports, df_flights, df_planes, visuals):
    st.header("Plane Type Analysis")
    st.subheader("Flight Distance vs. Arrival Delay (All Planes)")
    st.plotly_chart(visuals["fig_distance_vs_arr_delay"])
    plane_types = list(visuals["wind_vs_delay_by_type"].keys())
    selected_pt = st.selectbox("Select Plane Type for Detailed Analysis", plane_types)
    st.subheader(f"Wind Speed vs. Departure Delay for {selected_pt}")
    st.plotly_chart(visuals["wind_vs_delay_by_type"][selected_pt])
    st.subheader(f"Precipitation vs. Departure Delay for {selected_pt}")
    st.plotly_chart(visuals["precip_vs_delay_by_type"][selected_pt])
    st.subheader(f"Average Departure Delay by Airport & Flight Speed for {selected_pt}")
    st.plotly_chart(visuals["delay_airport_speed_by_type"][selected_pt])
