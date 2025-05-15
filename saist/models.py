from pydantic import BaseModel, Field
from typing import Annotated

class Finding(BaseModel):
    file: str
    snippet: Annotated[str, Field(description= "a single line code snipper containing the security issue") ]
    issue: str
    recommendation: str
    cwe: str
    priority: int
    line_number: int

class Findings(BaseModel):
    findings: list[Finding]

class FindingEnriched(Finding):
    file_contents: str

class FindingContext(Finding):
    context: str
    context_start: int
    context_end: int