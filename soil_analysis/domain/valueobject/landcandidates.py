from typing import List

from soil_analysis.domain.valueobject.land import Land


class LandCandidates:
    def __init__(self, candidates: List[Land] = None):
        if candidates is None:
            candidates = []
        self._land_list: List[Land] = candidates

    def add(self, land: Land):
        self._land_list.append(land)

    def search(self, name: str) -> Land:
        for land in self._land_list:
            if land.name == name:
                return land
        raise ValueError(f"Land '{name}' not found")

    def list(self) -> List[Land]:
        return self._land_list
