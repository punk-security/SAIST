import asyncio
import json
from typing import Any, override

from ..roles import Message, MessageRole
from ..tools import Tool
from . import APIAdapter


class BedrockConverseAdapter(APIAdapter):

    client: Any  # boto3.client("bedrock-runtime")

    @override
    def tools_to_provider(self, tools: list[Tool]) -> list[dict]:
        from copy import deepcopy

        bedrock_tools: list[dict] = []

        for tool in tools:
            properties: dict[str, Any] = {}

            for argument in tool.definition.arguments:
                schema = deepcopy(argument.schema)

                if argument.description and "description" not in schema:
                    schema["description"] = argument.description

                if argument.has_default:
                    default = argument.default
                    if default is None or isinstance(
                        default, (str, int, float, bool, list, dict)
                    ):
                        schema.setdefault("default", default)

                properties[argument.name] = schema

            bedrock_tools.append(
                {
                    "toolSpec": {
                        "name": tool.definition.name,
                        "description": tool.definition.description,
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": properties,
                                "required": [
                                    argument.name
                                    for argument in tool.definition.arguments
                                    if argument.required
                                ],
                                "additionalProperties": False,
                            }
                        },
                    }
                }
            )

        return bedrock_tools

    def _messages_to_bedrock_input(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system: str | None = None
        bedrock_messages: list[dict[str, Any]] = []

        def append_block(role: str, block: dict[str, Any]) -> None:
            if bedrock_messages and bedrock_messages[-1]["role"] == role:
                bedrock_messages[-1]["content"].append(block)
            else:
                bedrock_messages.append({"role": role, "content": [block]})

        for message in messages:
            match message:
                case MessageRole.System(content):
                    if system is not None:
                        raise ValueError("Multiple system messages specified in input")
                    system = content
                case MessageRole.User(content):
                    append_block("user", {"text": content})
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
                            "toolResult": {
                                "toolUseId": tool_call_id,
                                "content": [
                                    {"json": output}
                                    if isinstance(output, dict)
                                    else {"text": output if isinstance(output, str) else json.dumps(output)}
                                ],
                            }
                        },
                    )

        return system, bedrock_messages

    def _bedrock_output_to_messages(self, content: list[dict[str, Any]]) -> list[Message]:
        messages: list[Message] = []

        for block in content:
            if "text" in block:
                messages.append(MessageRole.Assistant(original=block))
            elif "toolUse" in block:
                tool_use = block["toolUse"]
                messages.append(
                    MessageRole.ToolCall(
                        tool_name=tool_use["name"],
                        tool_call_id=tool_use["toolUseId"],
                        arguments=tool_use["input"],
                        original=block,
                    )
                )
            elif "reasoningContent" in block:
                messages.append(MessageRole.Reasoning(original=block))
            else:
                raise ValueError(f"Unknown Bedrock content block: {sorted(block)}")

        return messages

    @override
    async def run(self, _input: list[Message], additional_tools: list[Tool] = []) -> list[Message]:
        system, messages = self._messages_to_bedrock_input(_input)
        tools = self.tools + self.tools_to_provider(additional_tools)

        kwargs: dict[str, Any] = {
            "modelId": self.model,
            "messages": messages,
            "inferenceConfig": {"maxTokens": 16384},
            "additionalModelRequestFields": {
                "reasoning_config": {"type": "enabled", "budget_tokens": 8192},
            },
        }
        if system is not None:
            kwargs["system"] = [{"text": system}]
        if tools:
            kwargs["toolConfig"] = {"tools": tools}

        response = await asyncio.to_thread(self.client.converse, **kwargs)

        return self._bedrock_output_to_messages(response["output"]["message"]["content"])
