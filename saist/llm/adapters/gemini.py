from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider

class GeminiAdapter(BaseLlmAdapter):
    def __init__(self, model: str = None, api_key: Optional[str] = None):
        if model is None:
            model = "gemini-2.5-pro-exp-03-25"
        self.model = GeminiModel(
            model,
            provider = GoogleGLAProvider( api_key=api_key )
        )
