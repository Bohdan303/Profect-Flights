import streamlit as st

def render(df_airports, visuals):
    st.header("General Maps")
    st.subheader("World Airport Map")
    st.plotly_chart(visuals.get("fig_alt"))
    st.subheader("US Airport Map")
    st.plotly_chart(visuals.get("fig_us"))
