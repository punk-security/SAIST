from typing import Optional, Callable, Type, List, Dict, Any
from llm.adapters import BaseLlmAdapter
import logging
from models import Finding, Findings

from pydantic import BaseModel

import re

logger = logging.getLogger(__name__)

class FaikeAdapter(BaseLlmAdapter):
    def __init__(self, base_url: str, model: str = None, api_key: Optional[str] = None):
        self.model = model
        self.model_name = self.model

    async def prompt_structured(self, system_prompt: str, user_prompt: str, response_format: Type[BaseModel], tool_fns: Optional[List[Callable]] = None) -> BaseModel:
        logger.getChild(self.__class__.__name__).debug("prompt_structured initial response", extra={'prompt': user_prompt})

        # Extract the real filename from user_prompt, allowing future steps to work
        filename: str = re.search("(?<=File: )(.*?)(?=\\n)", user_prompt).group(0)

        if response_format is Findings:
            fake_finding: dict[str: any] = {
                "file": filename,
                "snippet": "[]",
                "title": "Fake Issue #1234",
                "issue": "Fake Issue",
                "recommendation": "Do Nothing",
                "cwe": "CWE-NAN",
                "priority": 0,
                "line_number": 1,
            }
            
            return Findings(findings=[Finding.model_validate(fake_finding)])
            
        else: #Currently prompt_structured only accepts Findings as a return type
            logger.error(f"Invalid response_format {response_format} passed to prompt_structured (faike.py)")
            raise Exception(f"Invalid response_format {response_format} passed to prompt_structured (faike.py)")

        

    async def prompt(self, system_prompt: str, user_prompt: str, tool_fns: Optional[List[Callable]] = None) -> str | None:
        return "\nFake Summary"

    def generate_agent(self, system_prompt: str = None, tool_fns: Optional[List[Callable]] = None):
        #Faike LLM: Certified non-existent AI doesn't support interactive mode
        return None

