from typing import Optional

from llm.adapters import BaseLlmAdapter

from pydantic_ai.models.bedrock import BedrockConverseModel

class BedrockAdapter(BaseLlmAdapter):
    def __init__(self, model: str = None, api_key: Optional[str] = None):
        if api_key:
            raise ValueError("Do not provide API keys for AWS - use ENV variables")
        if model is None:
            model = "anthropic.claude-3-sonnet-20240229-v1:0"
        self.model = BedrockConverseModel( model )
        self.model_name = self.model.model_name
        self.model_vendor = 'Bedrock'


