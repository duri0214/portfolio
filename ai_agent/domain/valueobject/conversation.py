from dataclasses import dataclass


@dataclass
class EntityVO:
    name: str
    next_turn: float
