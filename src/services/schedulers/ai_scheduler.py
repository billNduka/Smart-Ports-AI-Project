import math
from typing import List
from datetime import datetime, timedelta
from ortools.sat.python import cp_model

from src.models import Vessel, Berth, Assignment
from src.services.schedulers.base_scheduler import BaseScheduler

class AIScheduler(BaseScheduler):
    """
    Implements AI-optimized scheduling logic using Google OR-Tools (CP-SAT Solver) 
    to minimize the total wait time of all vessels subject to capacity constraints.
    """

    def schedule(self, vessels: List[Vessel], berths: List[Berth]) -> List[Assignment]:
        if not vessels or not berths:
            return []

        model = cp_model.CpModel()

        # 1. Time Normalization
        # The OR-Tools solver strictly requires integers. We establish a "base time" (T=0)
        # and convert all datetimes and durations into discrete integers (minutes).
        base_time = min(
            min((v.arrival_time for v in vessels), default=datetime.max),
            min((b.available_from for b in berths), default=datetime.max)
        )

        # Calculate a safe mathematical horizon (the maximum possible time needed if all ships queue at one berth)
        max_arrival_min = max(int((v.arrival_time - base_time).total_seconds() // 60) for v in vessels)
        max_berth_min = max(int((b.available_from - base_time).total_seconds() // 60) for b in berths)
        total_handling_min = sum(int(v.handling_time * 60) for v in vessels)
        horizon = int(max(max_arrival_min, max_berth_min) + total_handling_min + 1440) # 24hr buffer added

        # 2. Variable Storage
        starts = {}
        ends = {}
        presences = {}
        intervals = {}
        wait_times = []

        for v in vessels:
            v_arrival_min = int((v.arrival_time - base_time).total_seconds() // 60)
            v_handling_min = int(v.handling_time * 60)
            
            # Master start and end time variables for this specific vessel
            start_var = model.NewIntVar(v_arrival_min, horizon, f"start_{v.vessel_id}")
            end_var = model.NewIntVar(v_arrival_min + v_handling_min, horizon, f"end_{v.vessel_id}")
            
            # The wait time is the difference between when it docks (start_var) and when it arrived
            wait_var = model.NewIntVar(0, horizon, f"wait_{v.vessel_id}")
            model.Add(wait_var == start_var - v_arrival_min)
            wait_times.append(wait_var)
            
            starts[v.vessel_id] = start_var
            ends[v.vessel_id] = end_var
            
            vessel_berth_presences = []
            
            for b in berths:
                # 3. Constraint: Physical Capacity & Cargo Matching
                if v.is_compatible_with_berth(b.capacity, b.compatible_cargo_types):
                    b_avail_min = int((b.available_from - base_time).total_seconds() // 60)
                    
                    # Boolean variable (1 if vessel docks here, 0 if not)
                    presence_var = model.NewBoolVar(f"presence_{v.vessel_id}_{b.berth_id}")
                    presences[(v.vessel_id, b.berth_id)] = presence_var
                    vessel_berth_presences.append(presence_var)
                    
                    # Optional interval strictly enforced if the solver sets presence_var to 1
                    opt_start = model.NewIntVar(v_arrival_min, horizon, f"opt_start_{v.vessel_id}_{b.berth_id}")
                    opt_end = model.NewIntVar(v_arrival_min + v_handling_min, horizon, f"opt_end_{v.vessel_id}_{b.berth_id}")
                    opt_interval = model.NewOptionalIntervalVar(
                        opt_start, v_handling_min, opt_end, presence_var, f"opt_int_{v.vessel_id}_{b.berth_id}"
                    )
                    
                    intervals.setdefault(b.berth_id, []).append(opt_interval)
                    
                    # Link the global start/end to this berth's optional start/end if selected
                    model.Add(start_var == opt_start).OnlyEnforceIf(presence_var)
                    model.Add(end_var == opt_end).OnlyEnforceIf(presence_var)
                    
                    # Constraint: The ship cannot dock before the berth is actually empty
                    model.Add(opt_start >= b_avail_min).OnlyEnforceIf(presence_var)
            
            # Constraint: A vessel must be assigned to EXACTLY one compatible berth
            if vessel_berth_presences:
                model.AddExactlyOne(vessel_berth_presences)
        
        # 4. Constraint: Non-Overlap
        # Ensures no two vessels can occupy the same berth at the same exact time
        for b in berths:
            if b.berth_id in intervals:
                model.AddNoOverlap(intervals[b.berth_id])
                
        # 5. Objective Function: Minimize Total Wait Time
        model.Minimize(sum(wait_times))
        
        # 6. Execute Solver
        solver = cp_model.CpSolver()
        # Optional: Limit search time in case of massive data sets
        solver.parameters.max_time_in_seconds = 30.0 
        status = solver.Solve(model)
        
        # 7. Extract Results back into Object-Oriented Domain Models
        assignments = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for v in vessels:
                for b in berths:
                    if (v.vessel_id, b.berth_id) in presences:
                        # Check if the AI chose this specific vessel-berth combination
                        if solver.Value(presences[(v.vessel_id, b.berth_id)]):
                            # Convert integer minutes back to Python datetimes
                            final_start_min = solver.Value(starts[v.vessel_id])
                            final_end_min = solver.Value(ends[v.vessel_id])
                            
                            start_time = base_time + timedelta(minutes=final_start_min)
                            end_time = base_time + timedelta(minutes=final_end_min)
                            
                            assignment = Assignment(
                                vessel_id=v.vessel_id,
                                berth_id=b.berth_id,
                                start_time=start_time,
                                end_time=end_time
                            )
                            assignments.append(assignment)
                            
                            # Update the berth object for accurate metric tracking later
                            b.available_from = end_time

        return assignments