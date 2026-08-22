from openai import AsyncOpenAI
from ..roles import Message, MessageRole
from ..tools import Tool, strict_schema
from typing import Any, override
from . import APIAdapter

import json

class OpenAIResponsesAdapter(APIAdapter):
    """
    A generic adapter over any OpenAI Responses compatible API.

    Implements only the non-stateful responses API to maximise compatibility across third-party providers (Ollama, llama.cpp, etc.)
    """
    client: AsyncOpenAI

    @override
    def tools_to_provider(self, tools: list[Tool]) -> list[dict]:
        from copy import deepcopy

        openai_tools: list[dict] = []

        for tool in tools:
            properties: dict[str, Any] = {}

            for argument in tool.definition.arguments:
                schema = deepcopy(argument.schema)

                # The argument description is normally already present in the
                # schema. This fallback handles custom ToolArgument instances or
                # schemas produced by external code.
                if (
                    argument.description
                    and "description" not in schema
                ):
                    schema["description"] = argument.description

                # Preserve the Python default as documentation where possible.
                # Do not emit arbitrary Python objects into JSON schema.
                if argument.has_default:
                    default = argument.default

                    if default is None or isinstance(
                        default,
                        (str, int, float, bool, list, dict),
                    ):
                        schema.setdefault("default", default)

                properties[argument.name] = schema

            parameters: dict[str, Any] = {
                "type": "object",
                "properties": properties,
                "required": [
                    argument.name
                    for argument in tool.definition.arguments
                    if argument.required
                ],
                "additionalProperties": False,
            }

            # OpenAI strict mode requires every property to be required. Optional
            # Python values should therefore be represented as nullable schemas.
            #
            # If your existing strict_schema() performs this normalization, use it
            # here. It should recurse through properties, arrays, and anyOf.
            parameters = strict_schema(parameters)

            openai_tools.append(
                {
                    "type": "function",
                    "name": tool.definition.name,
                    "description": tool.definition.description,
                    "parameters": parameters,
                    "strict": True,
                }
            )

        return openai_tools

    def _messages_to_openai_input(self, messages: list[Message]) -> list[Any]:
        _input: list[dict[str, Any]] = []

        have_developer = False

        for message in messages:
            match message:
                case MessageRole.System(content):
                    if have_developer:
                        raise ValueError("Multiple system messages specified in input")
                    _input.append({
                        "role": "system",
                        "content": content
                    })
                    have_developer = True
                case MessageRole.User(content):
                    _input.append({
                        "role": "user",
                        "content": content
                    })
                case MessageRole.Assistant(original):
                    _input.append(original)
                case MessageRole.Reasoning(original):
                    _input.append(original)
                case MessageRole.ToolCall(original=original):
                    _input.append(original)
                case MessageRole.ToolResponse(tool_call_id, output):
                    _input.append({
                        "type": "function_call_output",
                        "call_id": tool_call_id,
                        "output": json.dumps(output)
                    })

        return _input

    def _openai_output_to_messages(self, output: list[Any]) -> list[Message]:
        messages: list[Message] = []

        for item in output:
            match item.type:
                case "message":
                    messages.append(
                        MessageRole.Assistant(
                            original=item.model_dump()
                        )
                    )

                case "function_call":
                    as_dict = item.model_dump()
                    messages.append(
                        MessageRole.ToolCall(
                            tool_name=item.name,
                            tool_call_id=item.call_id,
                            arguments=json.loads(item.arguments),
                            original={
                                "type": "function_call",
                                "call_id": as_dict['call_id'],
                                "name": as_dict['name'],
                                "arguments": as_dict['arguments'],
                            }
                        )
                    )

                case "reasoning":
                    as_dict = item.model_dump()
                    del as_dict["status"]
                    messages.append(
                        MessageRole.Reasoning(
                            original=as_dict
                        )
                    )

                case _:
                    raise ValueError(f"Unknown OpenAI output type: {item.type}")

        return messages

    @override
    async def run(self, _input: list[Message], additional_tools: list[Tool] = []) -> list[Message]:
        response = await self.client.responses.create(
            model=self.model,
            reasoning={"effort":"medium"},
            tools=self.tools + self.tools_to_provider(additional_tools),
            input=self._messages_to_openai_input(_input),
        )

        return self._openai_output_to_messages(response.output)
