import asyncio

from llm.tools import Tool
from llm.roles import MessageRole

from . import SAISTStrategy
from file.null import NullProvider

from saistrun import SAISTRun

from functools import partial

import events

class SummaryStrategy(SAISTStrategy):
    """
    Strategy to enable the production of a summary at the end of a run.
    """

    _summary_flag = False
    _summary_lock = asyncio.Lock()

    def __init__(self, run: SAISTRun, summary_mode: bool = False):
        super().__init__(run)
        self.summary_mode = summary_mode

    @staticmethod
    async def create_summary(_run: SAISTRun, _strategy: "SummaryStrategy", summary: str):
        """
        Provide a summary based on the findings provided.
        """

        _run.set_output("summary", summary)
        await _run.terminate_run(force=True)

    @property
    def tools(self) -> list[Tool]:
        if self.summary_mode:
            return [
                Tool(self.create_summary)
            ]
        else:
            return []

    @property
    def system_prompt_part(self) -> str:
        if self.summary_mode:
            prompt = """
You are operating in summary-creation mode. Your goal here is to produce a summary based on the provided findings. This summary should be suitable for use in a PR review body.

"""
            for f in self.run.get_output("findings", []):
                validation_steps = "\n".join(f"    - {step}" for step in f.validation_steps) or "    - Not provided"
                prompt += (
                    f"- **File**: `{f.file}`\n"
                    f"  - **Issue**: {f.issue}\n"
                    f"  - **Recommendation**: {f.recommendation}\n"
                    f"  - **Validation steps**:\n{validation_steps}\n\n"
                )

            return prompt
        else:
            return ""

    async def handle_event(self, event: events.SAISTEvent) -> events.SAISTEventResponse | None:
        match event:
            case events.BeforeFinalizeRun():
                if not self.summary_mode:
                    async with self._summary_lock:
                        if not self._summary_flag:
                            self._summary_flag = True
                            run = await SAISTRun.create(self.run._model_interface, NullProvider(), [partial(type(self), summary_mode=True)])
                            await run.run_until_finished()
                else:
                    return events.Prevent("You must provide a summary to terminate this run.")

        return events.Skip()
