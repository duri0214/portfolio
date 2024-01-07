from abc import ABC, abstractmethod
from typing import Tuple


class BaseCoords(ABC):
    @abstractmethod
    def get_coords(self, to_str: bool = False) -> Tuple[float, float] or str:
        pass
