from pydantic import BaseModel, Field
from typing import Annotated

class Finding(BaseModel):
    file: str
    category: str
    snippet: Annotated[str, Field(description= "the single line of code snippet from the file most relevant to the detected issue") ]
    issue: str
    recommendation: str
    cwe: str
    priority: int
    line_number: int

class Findings(BaseModel):
    findings: list[Finding]

class FindingEnriched(Finding):
    file_contents: str
