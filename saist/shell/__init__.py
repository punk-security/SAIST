from llm.adapters import BaseLlmAdapter
from models import Finding
from scm import Scm
from scm.adapters import BaseScmAdapter

from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.markdown import CodeBlock, Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt

from pydantic_ai.messages import PartDeltaEvent, TextPartDelta

import logging

logger = logging.getLogger(__name__)

class Shell():
    PROMPT = """
    You are an AI agent helping someone understand their security findings.
    You can retrieve files if you need more context.
    Answer informally.
    You are able to get the list of findings if you need them.
    If you need to update them then use the tool to update the entire findings structure.
    If the user wants to quit, use the stop tool
    When asked about a finding, do not attempt to find more unless asked to do so
    If the user wishes, you can reset findings back to how they were at the start, and use a tool to clear chat context
    When asked to show findings, always display findings in a markdown table. paginate to 10 findings at a time
    """
    def __init__(self, llm: BaseLlmAdapter, scm: Scm, findings: list[Finding]):
        self.llm = llm
        self.scm = scm
        self.findings = findings
        self.original_findings = findings
        self.should_stop = False
        self.agent = llm.generate_agent(self.PROMPT, [self.stop, self.get_findings, self.update_findings, self.reset_findings, self.reset_chat, scm.read_file_contents])
        self.new_messages = None
        self.console = Console()
    
    async def run(self):
        print("Starting interactive shell with the LLM")
        self.print_all_findings()
        self.console.log("Greetings! How can I help? Let me know when we're done", style='green')
        while (self.should_stop != True):
            prompt = ""
            message = ""
            while prompt == "":
                prompt = self.console.input("#> ")
            with Live('', console=self.console, vertical_overflow='visible') as live:
                async with self.agent.iter(prompt, message_history=self.new_messages) as agent_run:
                    async for node in agent_run:
                        if self.agent.is_model_request_node(node):
                            async with node.stream(agent_run.ctx) as request_stream:
                                async for event in request_stream:
                                    if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                                        message += event.delta.content_delta
                                        live.update(Markdown(message))
                    self.new_messages = agent_run.result.all_messages()
        
    async def stop(self) -> None:
        """
        Closes the session for the user, they could call exit or goodbye etc

        """
        logger.info("LLM wants to stop")
        self.should_stop = True

    def print_all_findings(self) -> None:
        """
        Print all findings to screen

        """
        t = Table(*list(Finding.model_json_schema()["properties"].keys()))
        for finding in self.findings:
            t.add_row(*[f"{s}" for s in finding.model_dump().values()])
        self.console.print(t)

    async def get_findings(self) -> list[Finding]:
        """
        Asynchronously fetch all findings

        Returns:
        Findings: The full list of current findings
        """
        logger.info("LLM retrieving findings")
        return self.findings

    
    async def update_findings(self, findings: list[Finding]):
        """
        Asynchronously replaces all the current findins

        Parameters:
        Findings: The full list of current findings
        """
        logger.info("LLM updating findings")
        self.findings = findings

    async def reset_findings(self):
        """
        Reset findings back to how they were originally
        """
        logger.info("LLM resetting findings")
        self.findings = self.original_findings

    async def reset_chat(self):
        """
        Reset the chat context

        """
        logger.info("LLM cleared context window")
        self.new_messages = []
