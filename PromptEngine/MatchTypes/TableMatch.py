import json
from KG.SeekerTruther import Seeker
from KG.Chunks.TableChunk import TableTruther

class TextMatch:
    def __init__(self, s: Seeker):
        self.s = s

class TableDirectMatch(TextMatch):
    
    def __init__(self, s: Seeker, t_matches: list[tuple[TableTruther, str]]):
        super().__init__(s)
        self.t_matches = t_matches
    
    def __str__(self):
        res = {
            "seeker": self.s.textract_id,
            "matches": {
                truther.textract_id: reason for truther, reason in self.t_matches
            }
        }
        return json.dumps(res)
    
class IndirectMatch(TextMatch):
    
    def __init__(self, s: Seeker, t_matches: list[TableTruther], table_matches: list[str],
                 reasoning: str, calculation: str, is_correct: bool, error_type: str, recommended_change: str):
        super().__init__(s)
        self.table_matches = table_matches
        self.t_matches = t_matches
        self.reasoning = reasoning
        self.calculation = calculation
        self.is_correct = is_correct
        self.error_type = error_type
        self.recommended_change = recommended_change
    
    def __str__(self):
        res = {
            "seeker": self.s.textract_id,
            "reasoning": self.reasoning,
            "calculation": self.calculation,
            "is_correct": self.is_correct,
            "error_type": self.error_type,
            "recommended_change": self.recommended_change,
            "t_matches": [t.textract_id for t in self.t_matches],
            "table_matches": self.table_matches
        }
        return json.dumps(res)
    

class IndirectMatchV2(TextMatch):
    def __init__(self, s: Seeker, verify_id: str, long_reasoning: str, derivable: bool, 
                 reason: str, calculation_formula: str, calculation_references: list[dict[str, str]]):
        super().__init__(s)
        self.verify_id = verify_id
        self.long_reasoning = long_reasoning
        self.derivable = derivable
        self.reason = reason
        self.calculation_formula = calculation_formula
        self.calculation_references = calculation_references

    def __str__(self):
        res = {
            "seeker": self.s.textract_id,
            "verify_id": self.verify_id,
            "long_reasoning": self.long_reasoning,
            "derivable": self.derivable,
            "reason": self.reason,
            "calculation": {
                "formula": self.calculation_formula,
                "references": self.calculation_references
            }
        }
        return json.dumps(res, indent=4)    