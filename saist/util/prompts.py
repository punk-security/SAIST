import os
import yaml

class personality():
    def __init__(self, prompt_body, prompt_suffix = None, priority = None):
        self.prompt_body = prompt_body
        self.prompt_suffix = prompt_suffix
        if not priority:
            priority = 1
        self.priority = priority

    @property
    def PROMPT(self):
        return self.prompt_body + self.prompt_suffix

FILE_ANALYSIS_COMMON_SUFFIX = "Below is the diff for this single file. It starts with 'File: <filename>' followed by the unified diff.\n"

summary_writer = personality(
    prompt_body = """
    You are a senior application security engineer.
    Given the following list of findings (issue descriptions and recommendations)
    Write a concise but informative summary suitable for a GitHub Pull Request review comment.
    It should be just a few sentences.
    Group similar issues, and prioritize by severity. Use markdown formatting.
    Return only the markdown summary, no other text. Do not put the markdown inside ```
    """,
    prompt_suffix = "findings:" 
)

def load_personalities(file_path='saist.personalities'):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File '{file_path}' not found.")

    with open(file_path, 'r') as file:
        try:
            personalities = yaml.safe_load(file)
            if not isinstance(personalities, dict):
                raise ValueError("YAML content is not a dictionary.")

            for item_name, item_data in personalities.items():
                if not isinstance(item_data, dict):
                    raise ValueError(f"Item '{item_name}' must be a dictionary.")
                if 'priority' not in item_data:
                    raise ValueError(f"Item '{item_name}' is missing required field: 'priority'")
                if 'prompt' not in item_data:
                    raise ValueError(f"Item '{item_name}' is missing required field: 'prompt'")

            return personalities

        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")

personalities_dict = load_personalities()

analysts = {
    name: personality(
        data["prompt"], 
        f"Set the Category to {name}. Set CWE to the format CWE-XXX or N/A if a CWE is not relevant" + 
        FILE_ANALYSIS_COMMON_SUFFIX, priority=data["priority"]) 
        for name, data in personalities_dict.items()
}
