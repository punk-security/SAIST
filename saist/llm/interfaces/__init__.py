from ..tools import Tool
from ..adapters import APIAdapter
from typing import Any, AsyncGenerator, Callable, List, Optional, Type
from ..roles import Message, MessageRole

class ModelInterface:
    adapter: APIAdapter

    async def run(self, _input: list[Message], additional_tools: list[Tool] = []) -> list[Message]:
        return await self.adapter.run(_input, additional_tools)

    async def iter_run(self, _input: list[Message], additional_tools: list[Tool] = []) -> AsyncGenerator[Message, None]:
        messages = _input
        while True:
            output = await self.adapter.run(messages, additional_tools)
            messages.extend(output)
            for i in output:
                yield i

    def add_tools(self, tools: list[Tool]):
        self.adapter.add_tools(tools)

    #region SAIST Backwards Compatibility
    @property
    def model_name(self) -> str:
        return self.adapter.model

    async def prompt_structured(self, system_prompt: str, user_prompt: str, response_format: Type, tool_fns: Optional[List[Callable]] = None) -> Any:
        respond = Tool(
            lambda response:response,
            override_description="Use this tool to output the response to the prompt. A response through any other means will not be recognised or accepted.",
            override_name="respond", 
            override_types=[response_format]
        )

        additional_tools = [respond]

        tools_map = {
            tool.name: tool
            for tool in map(Tool, tool_fns or [])
        }
        additional_tools.extend(tools_map.values())

        if tool_fns is not None:
            for fn in tool_fns:
                additional_tools.append(Tool(fn))

        failed_responses = []

        response = None
        retries = 1

        while response is None and retries <= 3:
            messages = [
                MessageRole.System(system_prompt),
                MessageRole.User(user_prompt)
            ]
            async for message in self.iter_run(messages, additional_tools):
                match message:
                    case MessageRole.ToolCall(tool_name=name, arguments=arguments, tool_call_id=tool_call_id):
                        if name == "respond":
                            call = await respond.call(arguments)
                            if call['success']:
                                response = call['result']
                                break
                            else:
                                failed_responses.append((
                                    message,
                                    f"Failed to call tool `respond`: {call['error']}"
                                ))
                                retries += 1
                                break
                        else:
                            tool = tools_map.get(name) or self.adapter.tools_map.get(name)
                            if tool is None:
                                failed_responses.append((
                                    message,
                                    f"Attempted to call non-existent tool: {name}"
                                ))
                                retries += 1
                                break

                            call = await tool.call(arguments)
                            if not call['success']:
                                failed_responses.append((
                                    message,
                                    f"Failed to call tool `{name}`: {call['error']}"
                                ))
                                retries += 1
                                break

                            messages.append(MessageRole.ToolResponse(tool_call_id=tool_call_id, output=tool.serialize(call['result'])))

            if response is not None:
                break

        if response is None:
            print("\n".join(f"{output}: {call}" for (output, call) in failed_responses), flush=True)

        return response

    async def prompt(self, system_prompt: str, user_prompt: str, tool_fns: Optional[List[Callable]] = None) -> str | None:
        return await self.prompt_structured(system_prompt, user_prompt, str, tool_fns)
