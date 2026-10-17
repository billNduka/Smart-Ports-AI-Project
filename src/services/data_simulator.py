import random
from datetime import datetime, timedelta
from typing import List, Optional

from src.models import Vessel, Berth

# Fixed simulation clock: makes every run reproducible (no datetime.now()).
DEFAULT_START = datetime(2026, 10, 15, 18, 0, 0)


class IoTSimulator:
    """Simulates IoT data streams for arriving vessels and static port berths."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)  # isolated RNG (same sequence as random.seed(seed))
        self.cargo_types = ['Container', 'Bulk', 'Liquid', 'Ro-Ro', 'General']

    def generate_vessels(self, num_vessels: int, arrival_rate_per_hour: float = 2.0,
                         start_time: Optional[datetime] = None) -> List[Vessel]:
        """Poisson arrivals (exponential inter-arrival times), quantized to whole
        minutes; handling times are whole minutes too, so both schedulers see
        identical, exactly representable data."""
        start_time = start_time or DEFAULT_START
        vessels, clock_min = [], 0.0
        for i in range(1, num_vessels + 1):
            clock_min += self.rng.expovariate(arrival_rate_per_hour) * 60.0
            size = round(self.rng.uniform(20.0, 150.0), 2)
            handling_min = round(self.rng.uniform(2.0, 8.0) * 60.0)
            cargo = self.rng.choice(self.cargo_types)
            vessels.append(Vessel(
                vessel_id=f"VESSEL-{i:03d}",
                arrival_time=start_time + timedelta(minutes=round(clock_min)),
                size=size,
                cargo_type=cargo,
                handling_time=handling_min / 60.0,
            ))
        return vessels

    def generate_berths(self, num_berths: int, start_time: Optional[datetime] = None,
                        ensure_coverage: bool = False) -> List[Berth]:
        """ensure_coverage=True guarantees every cargo type has at least one berth
        that can take the largest vessel (150), so no vessel is rejected just
        because of the random berth draw."""
        start_time = start_time or DEFAULT_START
        berths = []
        for i in range(1, num_berths + 1):
            capacity = round(self.rng.uniform(50.0, 200.0), 2)
            cargos = self.rng.sample(self.cargo_types, self.rng.randint(1, 3))
            berths.append(Berth(berth_id=f"BERTH-{i:02d}", capacity=capacity,
                                compatible_cargo_types=cargos, available_from=start_time))
        if ensure_coverage and berths:
            # Every cargo type gets at least one berth that handles it AND is
            # large enough for the biggest vessel (150), so no ship is rejected
            # purely because of the random berth draw.
            for cargo in self.cargo_types:
                if not any(cargo in b.compatible_cargo_types and b.capacity >= 150.0 for b in berths):
                    target = berths[self.rng.randrange(len(berths))]
                    if cargo not in target.compatible_cargo_types:
                        target.compatible_cargo_types = list(target.compatible_cargo_types) + [cargo]
                    target.capacity = max(target.capacity, 150.0)
        return berths