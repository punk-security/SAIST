from typing import override

from . import ModelInterface
import boto3

from ..adapters.bedrock_converse import BedrockConverseAdapter
from ..tools import Tool

class BedrockInterface(ModelInterface):
    def __init__(
        self,
        tools: list[Tool],
        model: str | None = None,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        api_override: str | None = None,
    ):
        self.adapter = BedrockConverseAdapter(
            client=boto3.client(
                "bedrock-runtime",
                region_name=region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                endpoint_url=api_override,
            ),
            model=model or "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            tools=tools
        )
