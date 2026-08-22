from dataclasses import dataclass
from typing import Any

class MessageRole:
    @dataclass
    class System:
        """
        The system prompt; set once at the start of any conversation, some APIs expose this
        """
        content: str

    @dataclass
    class User:
        """
        A "user" message - in this context, represents unstructured, natural language queries from the harness to the model
        """
        content: str 

    @dataclass
    class Assistant:
        """
        An "assistant" message - in this context, represents unstructured, natural language conversation the model is having with itself, as not all models use reasoning for this. Opaque.
        """
        original: dict

    @dataclass
    class Reasoning:
        """
        A "reasoning" message - represents the model's reasoning traces. Opaque.
        """
        original: dict

    @dataclass
    class ToolCall:
        """
        An instance of the model requesting that the harness executes some tool provided to it
        """
        tool_name: str
        tool_call_id: str
        arguments: dict

        original: dict

    @dataclass
    class ToolResponse:
        """
        An instance of the harness responding with the result of executing a tool
        """
        tool_call_id: str
        output: Any

Message = MessageRole.System | MessageRole.User | MessageRole.Assistant | MessageRole.Reasoning | MessageRole.ToolCall | MessageRole.ToolResponse
