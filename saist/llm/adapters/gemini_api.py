from google import genai
from google.genai import types
from typing import Any, override

from ..roles import Message, MessageRole
from ..tools import Tool
from . import APIAdapter


class GeminiAdapter(APIAdapter):
    client: genai.Client

    @override
    def tools_to_provider(self, tools: list[Tool]) -> list[dict]:
        from copy import deepcopy

        functions = set()
        declarations: list[dict[str, Any]] = []

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
                        default, (str, int, float, bool, list, dict)
                    ):
                        schema.setdefault("default", default)

                properties[argument.name] = schema

            declarations.append(
                {
                    "name": tool.definition.name,
                    "description": tool.definition.description,
                    "parameters_json_schema": {
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

        return [{"function_declarations": declarations}] if declarations else []

    def _messages_to_gemini_input(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system: str | None = None
        contents: list[dict[str, Any]] = []

        def append_part(role: str, part: dict[str, Any]) -> None:
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": role, "parts": [part]})

        for message in messages:
            match message:
                case MessageRole.System(content):
                    if system is not None:
                        raise ValueError("Multiple system messages specified in input")
                    system = content
                case MessageRole.User(content):
                    append_part("user", {"text": content})
                case MessageRole.Assistant(original):
                    append_part("model", original)
                case MessageRole.Reasoning(original):
                    append_part("model", original)
                case MessageRole.ToolCall(original=original):
                    append_part("model", original)
                case MessageRole.ToolResponse(tool_call_id, output):
                    name, _, call_id = tool_call_id.partition("#")
                    function_response: dict[str, Any] = {
                        "name": name,
                        "response": output
                        if isinstance(output, dict)
                        else {"result": output},
                    }
                    if call_id:
                        function_response["id"] = call_id
                    append_part("user", {"function_response": function_response})

        if not isinstance(messages[-1], MessageRole.User):
            # Workaround for Gemini generate content not supporting 
            append_part("user", {"text": "Continue."})

        return system, contents

    def _gemini_output_to_messages(self, parts: list[Any]) -> list[Message]:
        messages: list[Message] = []

        for part in parts:
            original = part.model_dump(exclude_none=True)

            if part.function_call is not None:
                call = part.function_call
                messages.append(
                    MessageRole.ToolCall(
                        tool_name=call.name,
                        tool_call_id=f"{call.name}#{call.id}" if call.id else call.name,
                        arguments=dict(call.args or {}),
                        original=original,
                    )
                )
            elif part.thought:
                messages.append(MessageRole.Reasoning(original=original))
            elif part.text is not None:
                messages.append(MessageRole.Assistant(original=original))
            else:
                raise ValueError(f"Unknown Gemini content part: {original}")

        return messages

    @override
    async def run(self, _input: list[Message], additional_tools: list[Tool] = []) -> list[Message]:
        system, contents = self._messages_to_gemini_input(_input)

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents, # type: ignore
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=self.tools + self.tools_to_provider(additional_tools),
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=8192,
                ),
            ),
        )

        return self._gemini_output_to_messages(response.candidates[0].content.parts or []) # type: ignore
