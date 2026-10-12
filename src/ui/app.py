import copy
import sys
from pathlib import Path

import streamlit as st

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the engines we built in the Service Layer
from src.services.data_simulator import IoTSimulator
from src.services.schedulers.fcfs_scheduler import FCFSScheduler
from src.services.schedulers.ai_scheduler import AIScheduler
from src.services.metrics_engine import MetricsCalculator

def main():
    # Configure the main Streamlit page
    st.set_page_config(page_title="AI Smart Port Scheduler", layout="wide")
    
    st.title("🚢 AI-Powered Berth Allocation & Scheduling System")
    st.markdown("Comparing First-Come-First-Served (FCFS) vs. AI Constraint Programming for Nigerian Smart Ports.")
    
    # FR-7: Allow the user to adjust scenario parameters 
    st.sidebar.header("Simulation Parameters")
    num_vessels = st.sidebar.slider("Number of Vessels", min_value=5, max_value=50, value=15)
    num_berths = st.sidebar.slider("Number of Berths", min_value=1, max_value=10, value=3)
    arrival_rate = st.sidebar.slider("Arrival Rate (vessels/hr)", min_value=0.5, max_value=5.0, value=2.0)
    seed = st.sidebar.number_input("Random Seed (for reproducibility)", value=42, step=1)
    
    if st.sidebar.button("Run Simulation", type="primary"):
        with st.spinner("Generating IoT Data & Computing Schedules..."):
            
            # 1. Generate Data Layer (Phase 2)
            simulator = IoTSimulator(seed=int(seed))
            berths = simulator.generate_berths(num_berths=num_berths)
            vessels = simulator.generate_vessels(
                num_vessels=num_vessels, 
                arrival_rate_per_hour=arrival_rate
            )
            
            # 2. Run FCFS Scheduler (Phase 3)
            fcfs_engine = FCFSScheduler()
            # We must use copy.deepcopy() so the FCFS engine doesn't permanently 
            # overwrite the berth availability times before the AI engine gets a turn.
            fcfs_assignments = fcfs_engine.schedule(vessels, copy.deepcopy(berths))
            
            # 3. Run AI Scheduler (Phase 3)
            ai_engine = AIScheduler()
            ai_assignments = ai_engine.schedule(vessels, copy.deepcopy(berths))
            
            # 4. Compute Metrics (Phase 3)
            fcfs_metrics = MetricsCalculator.calculate_metrics(vessels, berths, fcfs_assignments)
            ai_metrics = MetricsCalculator.calculate_metrics(vessels, berths, ai_assignments)
            comparison = MetricsCalculator.compare_schedules(fcfs_metrics, ai_metrics)
            
            # ... (keep all the simulation and metric code above this line) ...
            
            # 5. Render UI
            from src.ui.components.kpi_dashboard import render_kpi_dashboard
            from src.ui.components.gantt_chart import render_gantt_chart
            
            st.success("Simulation Complete!")
            
            # Render the KPIs
            render_kpi_dashboard(fcfs_metrics, ai_metrics, comparison)
            
            st.divider()
            
            # Render the Gantt Charts
            st.subheader("⏱️ Schedule Visualizations")
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                render_gantt_chart(fcfs_assignments, title="Baseline (FCFS) Schedule")
            with chart_col2:
                render_gantt_chart(ai_assignments, title="AI-Optimized Schedule")

if __name__ == "__main__":
    main()