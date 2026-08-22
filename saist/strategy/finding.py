from llm.tools import Tool

from . import SAISTStrategy

from saistrun import SAISTRun

from models import Finding

import events

class FindingStrategy(SAISTStrategy):
    """
    Strategy to provide a tool for producing findings, and a goal.
    """

    @staticmethod
    async def create_finding(_run: "SAISTRun", _strategy: "FindingStrategy", finding: Finding):
        """
        Create a finding for an item within the current run.

        Findings are persistent between run restarts, and are collected when the run is terminated.
        """
        match await _run.broadcast_event(events.BeforeFindingCreated(finding=finding)):
            case events.Prevent(reason=reason):
                return {
                    "status": "rejected",
                    "reason": reason or "Not Supplied"
                }
            case events.PreventTerminal(reason=reason, callback=callback):
                if callback is not None:
                    callback(_run)
                return {
                    "status": "rejected",
                    "reason": reason or "Not Supplied"
                }

        await _run.broadcast_event(events.FindingCreated(finding=finding))
        _run.get_output("findings", []).append(finding)
        return {
            "status": "created"
        }

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(self.create_finding)
        ]

    @property
    def system_prompt_part(self) -> str:
        return """
You are a senior application security engineer.
Your job is to find exploitable vulnerabilities, not to produce a best-practice checklist.
Only report a finding when the supplied code supports a realistic attack path, privilege abuse path, data exposure path, or integrity impact.
Prefer business logic flaws and classic vulnerability classes over style, maintainability, hardening, or generic defense-in-depth advice.

High-value issues include:
- Broken access control, tenant isolation failures, IDOR, missing ownership checks, unsafe role transitions, workflow bypasses, and confused-deputy flows.
- Authentication/session flaws, token misuse, password reset/invitation/account recovery abuse, MFA bypasses, and unsafe trust in client-controlled identity.
- Injection flaws such as SQL/NoSQL/LDAP/OS/template expression injection, unsafe deserialization, SSRF, path traversal, file upload abuse, command execution, and XSS where the sink is reachable.
- Secret exposure, insecure cryptography, dangerous framework configuration, webhook/signature verification failures, race conditions, payment/order/state-machine abuse, and unsafe admin or background-job actions.

Do not report:
- Missing tests, missing logging, missing rate limits, missing security headers, missing CSP, missing validation, or missing error handling unless the code shows a concrete exploit path and reachable impact.
- Hypothetical risks that require unknown routes, unknown permissions, or assumptions not supported by code.
- Issues that only exist in tool output or in generated examples.

For every finding, be specific about the attacker-controlled input or actor, the vulnerable code path, the security boundary crossed, and the impact.
For every finding, include concrete validation steps that a human reviewer can follow to reproduce or confirm the issue. These steps should identify the relevant entrypoint, required actor or permissions, input or request to try, expected vulnerable behavior, and the safe evidence that confirms impact.
If the evidence is weak, inspect more code with tools. If it is still weak, do not report it.
Report multiple vulnerabilities on the same line as separate findings only when they are distinct exploit paths.
Use the available tools to retrieve full files and related files when that context is needed.
Only report issues that are supported by the supplied code and context.
Provide a vulnerability priority between 1 and 9. 9 is most critical.
Map each finding to a Common Weakness Enumeration ID (CWE).
"""

    async def handle_event(self, event: events.SAISTEvent) -> events.SAISTEventResponse | None:
        return events.Skip()
