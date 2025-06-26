from pydantic import BaseModel, Field
from typing import Annotated
from json import JSONEncoder, JSONDecoder

class Finding(BaseModel):
    file: str
    snippet: Annotated[str, Field(description= "a single line code snipper containing the security issue") ]
    title: Annotated[str, Field(description= "a short title describing the issue") ]
    issue: str
    recommendation: str
    cwe: Annotated[str, Field(description= "CWE id, should conform to CWE-XX or CWE-XXX where X is a number") ]
    priority: int
    line_number: int

class FindingJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Finding):
            return obj.__dict__
        return super().default(object)

class Findings(BaseModel):
    findings: list[Finding]

class FindingEnriched(Finding):
    file_contents: str

class FindingContext(Finding):
    context: str
    context_start: int
    context_end: int