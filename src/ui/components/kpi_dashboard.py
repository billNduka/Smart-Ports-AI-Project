import streamlit as st
from typing import Dict, Any

from src.services.metrics_engine import ScheduleMetrics

def render_kpi_dashboard(
    fcfs_metrics: ScheduleMetrics, 
    ai_metrics: ScheduleMetrics, 
    comparison: Dict[str, Any]
):
    """
    Renders the comparative performance metrics dashboard (FR-5).
    Displays KPIs side-by-side to highlight the AI optimization improvements.
    """
    st.subheader("📊 Performance Metrics Comparison")
    
    # 1. First Row: Wait Times (Lower is Better)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="FCFS Avg Wait (hrs)", 
            value=f"{fcfs_metrics.avg_wait_time_hours}h"
        )
    with col2:
        st.metric(
            label="AI Avg Wait (hrs)", 
            value=f"{ai_metrics.avg_wait_time_hours}h",
            delta=f"-{comparison['avg_wait_reduction_hours']}h ({comparison['avg_wait_reduction_pct']}%)",
            delta_color="inverse" # Tells Streamlit that a negative delta (reduction) is a 'good' (green) thing
        )
        
    with col3:
        st.metric(
            label="FCFS Max Wait (hrs)", 
            value=f"{fcfs_metrics.max_wait_time_hours}h"
        )
    with col4:
        st.metric(
            label="AI Max Wait (hrs)", 
            value=f"{ai_metrics.max_wait_time_hours}h",
            delta=f"-{comparison['max_wait_reduction_hours']}h",
            delta_color="inverse"
        )
        
    st.divider()
    
    # 2. Second Row: Utilization and Throughput (Higher is Better)
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            label="FCFS Berth Utilization", 
            value=f"{fcfs_metrics.berth_utilization_pct}%"
        )
    with col6:
        st.metric(
            label="AI Berth Utilization", 
            value=f"{ai_metrics.berth_utilization_pct}%",
            delta=f"+{comparison['utilization_improvement_pct']}%",
            delta_color="normal" # Tells Streamlit that a positive delta is a 'good' (green) thing
        )
        
    with col7:
        st.metric(
            label="FCFS Throughput", 
            value=f"{fcfs_metrics.total_throughput} ships"
        )
    with col8:
        # Throughput difference shouldn't change for a fixed batch, but we display it for completeness
        throughput_diff = ai_metrics.total_throughput - fcfs_metrics.total_throughput
        st.metric(
            label="AI Throughput", 
            value=f"{ai_metrics.total_throughput} ships",
            delta=f"{throughput_diff} ships" if throughput_diff != 0 else None,
            delta_color="normal"
        )