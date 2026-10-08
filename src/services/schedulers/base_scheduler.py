from abc import ABC, abstractmethod
from typing import List
from src.models import Vessel, Berth, Assignment

class BaseScheduler(ABC):
    """
    Abstract base class defining the standard interface for all scheduling engines.
    """

    @abstractmethod
    def schedule(self, vessels: List[Vessel], berths: List[Berth]) -> List[Assignment]:
        """
        Takes a list of incoming vessels and available berths, and returns
        a list of finalized Assignments.
        
        Must be implemented by any child class (e.g., FCFSScheduler, AIScheduler).
        """
        pass