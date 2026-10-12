import pandas as pd
import plotly.express as px
import streamlit as st
from typing import List

from src.models import Assignment

def render_gantt_chart(assignments: List[Assignment], title: str = "Berth Allocation Schedule"):
    """
    Takes a list of scheduled Assignments and renders an interactive Gantt chart 
    using Plotly Express, displaying berth occupancy over time (FR-6).
    """
    if not assignments:
        st.warning(f"No assignments to display for {title}.")
        return

    # 1. Convert Object-Oriented Domain Models into a Pandas DataFrame
    # Plotly requires a structured table (DataFrame) to generate visualizations.
    data = []
    for a in assignments:
        data.append({
            "Vessel": a.vessel_id,
            "Berth": a.berth_id,
            "Start Time": a.start_time,
            "End Time": a.end_time,
            # We calculate service duration strictly for the hover-over tooltip
            "Duration (Hours)": round((a.end_time - a.start_time).total_seconds() / 3600.0, 2)
        })
    
    df = pd.DataFrame(data)

    # 2. Generate the Plotly Timeline (Gantt Chart)
    fig = px.timeline(
        df, 
        x_start="Start Time", 
        x_end="End Time", 
        y="Berth", 
        color="Vessel", 
        title=title,
        hover_data=["Duration (Hours)"]
    )

    # 3. Format the Chart Layout
    # Plotly plots the Y-axis from bottom to top by default. We reverse it so 
    # Berth-01 appears at the top of the chart.
    fig.update_yaxes(autorange="reversed")
    
    # Customize the visual appearance for a professional dashboard look
    fig.update_layout(
        xaxis_title="Timeline",
        yaxis_title="Port Berths",
        showlegend=False, # Hiding legend since the vessel IDs are on the blocks
        margin=dict(l=20, r=20, t=40, b=20),
        height=400
    )

    # 4. Render the figure inside Streamlit
    st.plotly_chart(fig, width="stretch")