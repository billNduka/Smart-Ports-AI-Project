from dataclasses import dataclass
from datetime import datetime


@dataclass
class Assignment:
    """Represents a finalized berth allocation result for a single vessel."""

    vessel_id: str
    berth_id: str
    start_time: datetime
    end_time: datetime

    @property
    def wait_time_hours(self) -> float:
        """Calculates wait time in hours (difference between start time and arrival)."""
        # Derived property calculated when needed
        return 0.0  # Will be populated based on vessel arrival time