import asyncio
from pathlib import Path
from typing import override

from llm.tools import Tool

import events
from llm.roles import MessageRole
from saistrun import SAISTRun

from . import SAISTStrategy

class NaiveFileStrategy(SAISTStrategy):
    """
    A naive file-by-file strategy.
    """
    _files_lock = asyncio.Lock()
    _files: list[Path] | None = None

    @classmethod
    async def _get_next_file(cls) -> Path | None:
        assert cls._files is not None
        async with cls._files_lock:
            try:
                file = cls._files.pop()
                return file
            except:
                return None

    @staticmethod
    async def next_file(_run: SAISTRun, _strategy: "NaiveFileStrategy"):
        """
        Restart the run with a new file to analyse.

        This function clears the conversation and provides a new file to analyse. It does not provide additional context.

        Call this function when there is nothing further to action on the current file.
        """
        if _strategy.current_file is not None:
            await _run.broadcast_event(events.FileReviewed(_strategy.current_file))

        _strategy.current_file = await _strategy._get_next_file()
        if _strategy.current_file is not None:
            await _strategy.run.broadcast_event(events.StartReviewFile(_strategy.current_file))
        _strategy.restart_flag = True
        await _run.restart_run()

    @property
    @override
    def tools(self) -> list[Tool]:
        return [
            Tool(self.next_file)
        ]

    @property
    @override
    def system_prompt_part(self) -> str:
        return """
The following instructions relate to NaiveFileStrategy and its function `next_file`.

Unless otherwise stated, you have access to solely the NaiveFileStrategy provided file. This strategy provides one file per run, `next_file` restarts the run with a new file. Calling `next_file` will not provide additional context.
"""

    @override
    async def handle_event(self, event: events.SAISTEvent) -> events.SAISTEventResponse | None:
        match event:
            case events.RunInitialized():
                async with self._files_lock:
                    if self._files is None:
                        type(self)._files = self.run.files.copy()
                self.current_file = await self._get_next_file()
                if self.current_file is not None:
                    await self.run.broadcast_event(events.StartReviewFile(self.current_file))
            case events.BeforeRunStart():
                self.findings = 0
                self.skip_flag = False
                self.restart_flag = False

                if self.current_file is not None:
                    content = await self.run.read_file(self.current_file)
                    self.run.messages.append(MessageRole.User(f"""
Provided by: NaiveFileStrategy

File path: {self.current_file}

```
{content}
```
"""
                    ))
                else:
                    self.run.messages.append(MessageRole.User("""
Provided by: NaiveFileStrategy

There are no further files that can be provided by NaiveFileStrategy. Please terminate the run.
"""
                    ))
            case events.BeforeRestartRun():
                if not self.restart_flag:
                    return events.Prevent()

        return events.Skip()
