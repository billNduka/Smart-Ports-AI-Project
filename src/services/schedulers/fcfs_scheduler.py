from typing import List
from datetime import timedelta
from src.models import Vessel, Berth, Assignment
from src.services.schedulers.base_scheduler import BaseScheduler

class FCFSScheduler(BaseScheduler):
    """
    Implements the traditional First-Come-First-Served scheduling logic.
    """

    def schedule(self, vessels: List[Vessel], berths: List[Berth]) -> List[Assignment]:
        assignments = []
        
        # 1. Sort vessels strictly by arrival time (The core of FCFS)
        sorted_vessels = sorted(vessels, key=lambda v: v.arrival_time)
        
        # 2. Make a working copy of berths so we can update their availability times
        # without permanently altering the original objects passed in.
        working_berths = berths.copy()

        for vessel in sorted_vessels:
            best_berth = None
            earliest_available_time = None

            # 3. Find the first available berth that can handle this specific ship
            for berth in working_berths:
                if vessel.is_compatible_with_berth(berth.capacity, berth.compatible_cargo_types):
                    # If this is the first compatible berth we found, or if it becomes
                    # available earlier than the one we previously found, select it.
                    if earliest_available_time is None or berth.available_from < earliest_available_time:
                        best_berth = berth
                        earliest_available_time = berth.available_from
            
            # 4. If a compatible berth was found, calculate the start and end times
            if best_berth:
                # The ship cannot start service before it arrives, AND it cannot 
                # start before the berth is actually empty.
                start_time = max(vessel.arrival_time, best_berth.available_from)
                
                # End time is simply start time + handling time
                end_time = start_time + timedelta(hours=vessel.handling_time)
                
                # 5. Create the Assignment record
                assignment = Assignment(
                    vessel_id=vessel.vessel_id,
                    berth_id=best_berth.berth_id,
                    start_time=start_time,
                    end_time=end_time
                )
                assignments.append(assignment)
                
                # 6. Update the berth so the next ship knows it is occupied
                best_berth.available_from = end_time

        return assignments