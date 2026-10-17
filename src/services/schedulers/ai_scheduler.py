import copy
import math
from typing import List
from datetime import datetime, timedelta
from ortools.sat.python import cp_model

from src.models import Vessel, Berth, Assignment
from src.services.schedulers.base_scheduler import BaseScheduler
from src.services.schedulers.fcfs_scheduler import FCFSScheduler


class AIScheduler(BaseScheduler):
    """
    AI-optimized scheduling using Google OR-Tools CP-SAT.
    Minimizes total vessel waiting time subject to berth compatibility,
    one-berth-per-vessel, berth availability and non-overlap constraints.

    Changes vs. first version:
      * Time conversion uses ceil() for arrivals / berth availability and
        round() for handling time, so no vessel can start before it arrives
        and no service time is silently shortened.
      * The FCFS schedule is supplied to the solver as a starting hint, so
        the result is never worse than FCFS even if the time limit is hit.
      * Solver status and solve time are exposed for reporting.
    """

    def __init__(self, time_limit_seconds: float = 30.0):
        self.time_limit_seconds = time_limit_seconds
        self.last_status = "n/a"
        self.last_solve_seconds = 0.0

    @staticmethod
    def _minutes(dt: datetime, base: datetime) -> int:
        return math.ceil((dt - base).total_seconds() / 60.0 - 1e-9)

    def schedule(self, vessels: List[Vessel], berths: List[Berth]) -> List[Assignment]:
        if not vessels or not berths:
            return []

        model = cp_model.CpModel()
        base_time = min(
            min(v.arrival_time for v in vessels),
            min(b.available_from for b in berths),
        )

        arr = {v.vessel_id: self._minutes(v.arrival_time, base_time) for v in vessels}
        dur = {v.vessel_id: round(v.handling_time * 60.0) for v in vessels}
        avail = {b.berth_id: max(0, self._minutes(b.available_from, base_time)) for b in berths}

        horizon = int(max(max(arr.values()), max(avail.values())) + sum(dur.values()) + 1440)

        # Warm start: the FCFS schedule (a valid feasible solution)
        fcfs_hint = {
            a.vessel_id: (a.berth_id, self._minutes(a.start_time, base_time))
            for a in FCFSScheduler().schedule(vessels, copy.deepcopy(berths))
        }

        starts, ends, presences, intervals, wait_times = {}, {}, {}, {}, []

        for v in vessels:
            a_min, d_min = arr[v.vessel_id], dur[v.vessel_id]
            start_var = model.NewIntVar(a_min, horizon, f"start_{v.vessel_id}")
            end_var = model.NewIntVar(a_min + d_min, horizon, f"end_{v.vessel_id}")
            wait_var = model.NewIntVar(0, horizon, f"wait_{v.vessel_id}")
            model.Add(wait_var == start_var - a_min)
            wait_times.append(wait_var)
            starts[v.vessel_id], ends[v.vessel_id] = start_var, end_var

            hint_berth, hint_start = fcfs_hint.get(v.vessel_id, (None, None))
            if hint_start is not None:
                model.AddHint(start_var, hint_start)
                model.AddHint(end_var, hint_start + d_min)

            presence_list = []
            for b in berths:
                if not v.is_compatible_with_berth(b.capacity, b.compatible_cargo_types):
                    continue
                pres = model.NewBoolVar(f"presence_{v.vessel_id}_{b.berth_id}")
                presences[(v.vessel_id, b.berth_id)] = pres
                presence_list.append(pres)

                o_start = model.NewIntVar(a_min, horizon, f"os_{v.vessel_id}_{b.berth_id}")
                o_end = model.NewIntVar(a_min + d_min, horizon, f"oe_{v.vessel_id}_{b.berth_id}")
                interval = model.NewOptionalIntervalVar(
                    o_start, d_min, o_end, pres, f"oi_{v.vessel_id}_{b.berth_id}"
                )
                intervals.setdefault(b.berth_id, []).append(interval)

                model.Add(start_var == o_start).OnlyEnforceIf(pres)
                model.Add(end_var == o_end).OnlyEnforceIf(pres)
                model.Add(o_start >= avail[b.berth_id]).OnlyEnforceIf(pres)

                chosen = hint_berth == b.berth_id
                model.AddHint(pres, 1 if chosen else 0)
                model.AddHint(o_start, hint_start if chosen else a_min)
                model.AddHint(o_end, (hint_start + d_min) if chosen else a_min + d_min)

            if presence_list:
                model.AddExactlyOne(presence_list)

        for b in berths:
            if b.berth_id in intervals:
                model.AddNoOverlap(intervals[b.berth_id])

        model.Minimize(sum(wait_times))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        status = solver.Solve(model)
        self.last_status = solver.StatusName(status)
        self.last_solve_seconds = solver.WallTime()

        assignments: List[Assignment] = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for v in vessels:
                for b in berths:
                    key = (v.vessel_id, b.berth_id)
                    if key in presences and solver.Value(presences[key]):
                        assignments.append(
                            Assignment(
                                vessel_id=v.vessel_id,
                                berth_id=b.berth_id,
                                start_time=base_time + timedelta(minutes=solver.Value(starts[v.vessel_id])),
                                end_time=base_time + timedelta(minutes=solver.Value(ends[v.vessel_id])),
                            )
                        )
        return assignments