from pydantic import BaseModel

class Answer(BaseModel):
  explanation: str
  analysis: str