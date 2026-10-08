from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple


@dataclass
class Berth:
    """Represents a designated docking location at the port."""

    berth_id: str
    capacity: float  # Maximum vessel size accommodated
    compatible_cargo_types: List[str]  # Supported cargo types
    available_from: datetime = field(default_factory=datetime.now)

    def can_accommodate(self, vessel_size: float, cargo_type: str) -> bool:
        """Determines if a given vessel size and cargo type are supported."""
        size_ok = vessel_size <= self.capacity
        cargo_ok = cargo_type.lower() in [
            c.lower() for c in self.compatible_cargo_types
        ]
        return size_ok and cargo_ok