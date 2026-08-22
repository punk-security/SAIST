from anthropic import AsyncAnthropic, omit
from ..roles import Message, MessageRole
from ..tools import Tool
from typing import Any, override
from . import APIAdapter

import json


class AnthropicMessagesAdapter(APIAdapter):
    client: AsyncAnthropic
    max_tokens: int = 4096
    thinking_budget: int | None = None

    @override
    def tools_to_provider(self, tools: list[Tool]) -> list[dict]:
        from copy import deepcopy

        functions = set()
        anthropic_tools: list[dict] = []

        for tool in tools:
            if tool.name in functions:
                continue
            else:
                functions.add(tool.name)
            properties: dict[str, Any] = {}

            for argument in tool.definition.arguments:
                schema = deepcopy(argument.schema)

                if argument.description and "description" not in schema:
                    schema["description"] = argument.description

                if argument.has_default:
                    default = argument.default

                    if default is None or isinstance(
                        default,
                        (str, int, float, bool, list, dict),
                    ):
                        schema.setdefault("default", default)

                properties[argument.name] = schema

            anthropic_tools.append(
                {
                    "name": tool.definition.name,
                    "description": tool.definition.description,
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": [
                            argument.name
                            for argument in tool.definition.arguments
                            if argument.required
                        ],
                        "additionalProperties": False,
                    },
                }
            )

        return anthropic_tools

    def _messages_to_anthropic_input(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system: str | None = None
        anthropic_messages: list[dict[str, Any]] = []

        def append_block(role: str, block: dict[str, Any]) -> None:
            if anthropic_messages and anthropic_messages[-1]["role"] == role:
                anthropic_messages[-1]["content"].append(block)
            else:
                anthropic_messages.append({"role": role, "content": [block]})

        for message in messages:
            match message:
                case MessageRole.System(content):
                    if system is not None:
                        raise ValueError("Multiple system messages specified in input")
                    system = content
                case MessageRole.User(content):
                    append_block("user", {"type": "text", "text": content})
                case MessageRole.Assistant(original):
                    append_block("assistant", original)
                case MessageRole.Reasoning(original):
                    append_block("assistant", original)
                case MessageRole.ToolCall(original=original):
                    append_block("assistant", original)
                case MessageRole.ToolResponse(tool_call_id, output):
                    append_block(
                        "user",
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": output
                            if isinstance(output, str)
                            else json.dumps(output),
                        },
                    )

        return system, anthropic_messages

    def _anthropic_output_to_messages(self, content: list[Any]) -> list[Message]:
        messages: list[Message] = []

        for block in content:
            match block.type:
                case "text":
                    messages.append(
                        MessageRole.Assistant(
                            original=block.model_dump()
                        )
                    )

                case "tool_use":
                    messages.append(
                        MessageRole.ToolCall(
                            tool_name=block.name,
                            tool_call_id=block.id,
                            arguments=block.input,
                            original=block.model_dump(),
                        )
                    )

                case "thinking" | "redacted_thinking":
                    messages.append(
                        MessageRole.Reasoning(
                            original=block.model_dump()
                        )
                    )

                case _:
                    raise ValueError(
                        f"Unknown Anthropic content block type: {block.type}"
                    )

        return messages

    @override
    async def run(self, _input: list[Message], additional_tools: list[Tool] = []) -> list[Message]:
        system, messages = self._messages_to_anthropic_input(_input)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            thinking={"type": "enabled", "budget_tokens": 8192},
            tools=self.tools + self.tools_to_provider(additional_tools),
            messages=messages, # type: ignore
            system=system if system is not None else omit,
        )

        return self._anthropic_output_to_messages(response.content)
