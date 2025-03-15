from soil_analysis.domain.valueobject.land import LandLocation


class LandCandidates:
    def __init__(self, candidates: list[LandLocation] = None):
        if candidates is None:
            candidates = []
        self._land_list: list[LandLocation] = candidates

    def add(self, land: LandLocation):
        self._land_list.append(land)

    def search(self, name: str) -> LandLocation:
        for land in self._land_list:
            if land.name == name:
                return land
        raise ValueError(f"Land '{name}' not found")

    def list(self) -> list[LandLocation]:
        return self._land_list
