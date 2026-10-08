import random
from datetime import datetime, timedelta
from typing import List
from src.models import Vessel, Berth

class IoTSimulator:
    """Simulates IoT data streams for arriving vessels and static port berths."""
    
    def __init__(self, seed: int = 42):
        """
        Initializes the simulator with a fixed random seed (Task 2.4).
        Ensures scenarios are reproducible so both schedulers are tested fairly.
        """
        self.seed = seed
        random.seed(self.seed)
        
        # Cargo types strictly based on the thesis constraints
        self.cargo_types = ['Container', 'Bulk', 'Liquid', 'Ro-Ro', 'General']

    def generate_vessels(self, num_vessels: int, arrival_rate_per_hour: float = 2.0, start_time: datetime = None) -> List[Vessel]:
        """
        Generates a list of mock vessels using an exponential inter-arrival distribution.
        (Task 2.2)
        """
        if start_time is None:
            start_time = datetime.now()
            
        vessels = []
        current_time = start_time
        
        for i in range(1, num_vessels + 1):
            # Poisson process arrival (Exponential inter-arrival time)
            inter_arrival_hours = random.expovariate(arrival_rate_per_hour)
            current_time += timedelta(hours=inter_arrival_hours)
            
            # Apply thesis parameter constraints
            size = round(random.uniform(20.0, 150.0), 2)
            handling_time = round(random.uniform(2.0, 8.0), 2)
            cargo = random.choice(self.cargo_types)
            priority = random.randint(1, 3)
            
            # Instantiate the Domain Model (Coordinates removed)
            vessel = Vessel(
                vessel_id=f"VESSEL-{i:03d}",
                arrival_time=current_time,
                size=size,
                cargo_type=cargo,
                handling_time=handling_time,
                priority=priority
            )
            
            vessels.append(vessel)
            
        return vessels

    def generate_berths(self, num_berths: int) -> List[Berth]:
        """
        Generates a static list of port berths with varying capacities.
        (Task 2.3)
        """
        berths = []
        
        for i in range(1, num_berths + 1):
            # Thesis constraint: Capacities between 50 and 200
            capacity = round(random.uniform(50.0, 200.0), 2)
            
            # Randomly assign 1 to 3 compatible cargo types to each berth
            compatible_cargos = random.sample(self.cargo_types, random.randint(1, 3))
            
            # Instantiate the Domain Model (Coordinates removed)
            berth = Berth(
                berth_id=f"BERTH-{i:02d}",
                capacity=capacity,
                compatible_cargo_types=compatible_cargos,
                available_from=datetime.now() # Initially available right now
            )
            
            berths.append(berth)
            
        return berths