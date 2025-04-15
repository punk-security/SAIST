from rich.console import Console
from rich.markdown import Markdown
import random


async def poem(llm):
    llm.model_options = {'temperature': 1.0}
    console = Console(width=80)
    poem_type = random.choice(["haiku", "limerick","ode"", villanelle", "sonnet", "acrostic", "free verse", "ellegy", "ballad"])
    console.print(f"\nGenerating a wonderful {poem_type} poem..")
    console.print("\n")
    resp = await llm.prompt(f"""
                            Generate a short DevSecOps themed {poem_type} poem in markdown with emojis. 
                            Sign it with a made up DevSecOps themed poet name. 
                            """, "Do not include a title"
                            )
    resp = resp.removeprefix("```markdown")
    resp = resp.removesuffix("```")
    console.print(Markdown(resp))
    console.print("\n\n")
