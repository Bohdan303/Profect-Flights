import streamlit as st
import plotly.graph_objects as go
import pandas as pd

def render(df_airports, df_flights):
    st.header("Flight Routes")
    selected_airports = st.multiselect("Select destination airports (FAA codes)", sorted(df_flights["dest"].unique()), key="route_plan")
    if st.button("Plot Routes", key="plot_routes"):
        fig = go.Figure()
        if selected_airports:
            # Check if all selected airports are in the US
            us_only = all(df_airports[df_airports["faa"] == code]["country"].iloc[0] == "United States" for code in selected_airports)
            geo_scope = "usa" if us_only else None
            fig.update_layout(geo=dict(scope=geo_scope))
            # For example, use JFK as base for route lines
            for code in selected_airports:
                dest = df_airports[df_airports["faa"] == code]
                if not dest.empty:
                    dest = dest.iloc[0]
                    # Here, we assume at least one flight to that destination exists:
                    origin_code = df_flights[df_flights["dest"] == code]["origin"].iloc[0]
                    origin = df_airports[df_airports["faa"] == origin_code].iloc[0]
                    fig.add_trace(
                        go.Scattergeo(
                            locationmode="USA-states" if us_only else None,
                            lon=[origin["lon"], dest["lon"]],
                            lat=[origin["lat"], dest["lat"]],
                            mode="lines",
                            line=dict(width=2, color="red"),
                            name=f"{origin_code} to {code}",
                        )
                    )
        st.plotly_chart(fig)
