from lib.geo.valueobject.coord import LandCoords


class Land:
    def __init__(self, name, coords_str):
        self.name = name
        self.center = LandCoords(coords_str)
