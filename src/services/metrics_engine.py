from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

from src.models import Vessel, Berth, Assignment


@dataclass
class ScheduleMetrics:
    """Encapsulates key performance indicators (KPIs) for a single schedule."""
    total_vessels: int
    avg_wait_time_hours: float
    max_wait_time_hours: float
    total_throughput: int
    berth_utilization_pct: float


class MetricsCalculator:
    """
    Service class responsible for calculating and comparing KPIs 
    across different scheduling strategies (FR-5).
    """

    @staticmethod
    def calculate_metrics(
        vessels: List[Vessel],
        berths: List[Berth],
        assignments: List[Assignment]
    ) -> ScheduleMetrics:
        """
        Computes average wait time, max wait time, throughput, and berth utilization 
        for a given set of assignments.
        """
        if not assignments or not vessels:
            return ScheduleMetrics(
                total_vessels=0,
                avg_wait_time_hours=0.0,
                max_wait_time_hours=0.0,
                total_throughput=0,
                berth_utilization_pct=0.0
            )

        # 1. Map vessel IDs to vessel objects for quick lookup
        vessel_map = {v.vessel_id: v for v in vessels}

        wait_times_hours = []
        total_occupied_hours = 0.0

        min_start_time = None
        max_end_time = None

        # 2. Iterate through assignments to gather time deltas
        for assignment in assignments:
            vessel = vessel_map.get(assignment.vessel_id)
            if vessel:
                # Wait time = actual start time - vessel arrival time
                wait_seconds = (assignment.start_time - vessel.arrival_time).total_seconds()
                wait_hours = max(0.0, wait_seconds / 3600.0)
                wait_times_hours.append(wait_hours)

            # Service time on berth = end time - start time
            service_seconds = (assignment.end_time - assignment.start_time).total_seconds()
            total_occupied_hours += max(0.0, service_seconds / 3600.0)

            # Track overall timeline bounds across all berths
            if min_start_time is None or assignment.start_time < min_start_time:
                min_start_time = assignment.start_time
            if max_end_time is None or assignment.end_time > max_end_time:
                max_end_time = assignment.end_time

        # 3. Calculate aggregate KPIs
        total_serviced = len(assignments)
        avg_wait = (sum(wait_times_hours) / total_serviced) if total_serviced > 0 else 0.0
        max_wait = max(wait_times_hours) if wait_times_hours else 0.0

        # Berth Utilization = Total occupied berth hours / (Total time horizon * total berths)
        if min_start_time and max_end_time and len(berths) > 0:
            time_horizon_hours = (max_end_time - min_start_time).total_seconds() / 3600.0
            total_available_berth_hours = time_horizon_hours * len(berths)
            utilization_pct = (
                (total_occupied_hours / total_available_berth_hours) * 100.0
                if total_available_berth_hours > 0
                else 0.0
            )
        else:
            utilization_pct = 0.0

        return ScheduleMetrics(
            total_vessels=total_serviced,
            avg_wait_time_hours=round(avg_wait, 2),
            max_wait_time_hours=round(max_wait, 2),
            total_throughput=total_serviced,
            berth_utilization_pct=round(utilization_pct, 2)
        )

    @staticmethod
    def compare_schedules(
        fcfs_metrics: ScheduleMetrics,
        ai_metrics: ScheduleMetrics
    ) -> Dict[str, Any]:
        """
        Calculates absolute and percentage improvements achieved by AI over FCFS.
        """
        wait_reduction_hours = fcfs_metrics.avg_wait_time_hours - ai_metrics.avg_wait_time_hours
        wait_reduction_pct = (
            (wait_reduction_hours / fcfs_metrics.avg_wait_time_hours) * 100.0
            if fcfs_metrics.avg_wait_time_hours > 0
            else 0.0
        )

        max_wait_reduction_hours = fcfs_metrics.max_wait_time_hours - ai_metrics.max_wait_time_hours
        utilization_improvement_pct = ai_metrics.berth_utilization_pct - fcfs_metrics.berth_utilization_pct

        return {
            "avg_wait_reduction_hours": round(wait_reduction_hours, 2),
            "avg_wait_reduction_pct": round(wait_reduction_pct, 2),
            "max_wait_reduction_hours": round(max_wait_reduction_hours, 2),
            "utilization_improvement_pct": round(utilization_improvement_pct, 2)
        }