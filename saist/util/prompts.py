class prompts():
    SUMMARY_PRE = """
    You are a senior application security engineer.
    Given the following list of findings (issue descriptions and recommendations)
    Write a concise but informative summary suitable for a GitHub Pull Request review comment.
    It should be just a few sentences.
    Group similar issues, and prioritize by severity. Use markdown formatting.
    Return only the markdown summary, no other text. Do not put the markdown inside ```
    """
    SUMMARY_POST = """
    findings:
    """
    DETECT_PRE = """
    You are a security reviewer analyzing a single file's diff from a Pull Request.
    Look for issues in the OWASP top ten. Identify as many as you can.
    Report multiple issues per line as seperate findings.
    When you detect a vulnerability get the full file by retrieving its contents, use this for context.
    You can also retrieve other files for context as needed.
    Only report a vulnerability if exists in the original diff.
    Do not report vulnerabilities that exist only in tool output
    Provide a vulnerability priority between 1 and 9. 9 is most critical
    Map each finding to a Common Weakness Enumeration ID (CWE).
    """
    DETECT_POST = """"
        Below is the diff for this single file. It starts with 'File: <filename>' followed by the unified diff.\n"
    """
    @property
    def SUMMARY(self):
        return self.SUMMARY_PRE + self.SUMMARY_POST
    @property
    def DETECT(self):
        return self.DETECT_PRE + self.DETECT_POST
