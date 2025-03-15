from lib.geo.valueobject.coord import LandLocation


class Land:
    def __init__(self, name, coords_str):
        self.name = name
        self.center = LandLocation(coords_str)
