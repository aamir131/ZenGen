import json
from KG.SeekerTruther import Seeker, ChartTruther

class ChartMatch:
    def __init__(self, s: Seeker):
        self.s = s

class ChartDirectMatch(ChartMatch):
    
    def __init__(self, s: Seeker, t_matches: list[tuple[ChartTruther, str]]):
        super().__init__(s)
        self.t_matches = t_matches
    
    def __str__(self):
        res = {
            "seeker": self.s.textract_id,
            "matches": {
                chart_truther.textract_id: reason for chart_truther, reason in self.t_matches
            }
        }
        return json.dumps(res)