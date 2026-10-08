from dataclasses import dataclass
from datetime import datetime
from typing import Tuple


@dataclass
class Vessel:
    """Represents an incoming vessel requesting berth allocation."""

    vessel_id: str
    arrival_time: datetime
    size: float  # Length or tonnage
    cargo_type: str  # e.g., 'container', 'bulk', 'tanker'
    handling_time: float  # Unloading/loading time in hours
    
    def is_compatible_with_berth(
        self, berth_capacity: float, supported_cargos: list[str]
    ) -> bool:
        """Checks if the vessel fits within a berth's capacity and cargo constraints."""
        fits_capacity = self.size <= berth_capacity
        supports_cargo = self.cargo_type.lower() in [
            c.lower() for c in supported_cargos
        ]
        return fits_capacity and supports_cargo