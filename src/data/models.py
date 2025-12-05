from dataclasses import dataclass, asdict

@dataclass
class PlayerScore:
    season: int
    ign: str
    topscore: int
    totalscore: int

    def to_dict(self):
        return asdict(self)
