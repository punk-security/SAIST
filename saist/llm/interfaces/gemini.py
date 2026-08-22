from . import ModelInterface
from google import genai
from google.genai import types

from ..adapters.gemini_api import GeminiAdapter
from ..tools import Tool

class GeminiInterface(ModelInterface):
    def __init__(self, api_key: str, tools: list[Tool], model: str | None = None, api_override: str | None = None):
        self.adapter = GeminiAdapter(
            client=genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(base_url=api_override) if api_override else None,
            ),
            model=model or "gemini-2.5-pro",
            tools=tools
        )
