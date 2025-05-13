import os
import yaml
import logging

logger = logging.getLogger(__name__) 

class PromptRules:
    RulesFile = "saist.rules"

    @staticmethod
    def apply_rules(pre_prompt: str, post_prompt: str = "") -> str:
        rules = PromptRules.load_rules()
    
        override = rules.get("PROMPT_OVERRIDE")
        pre = rules.get("PROMPT_PRE", "")
        post = rules.get("PROMPT_POST", "")

        final_prompt = override if override else (pre_prompt + post_prompt) #if override isn't specified, this should just use the prefix and suffix with the orig prompt
        return f"{pre}{final_prompt}{post}"


    @staticmethod
    def load_rules():
        if not os.path.exists(PromptRules.RulesFile):
            logger.warning("No saist.rules file found.")
            return {} #return empty rules

        try:
            with open(PromptRules.RulesFile, 'r') as file:
                yaml_content = file.read()
                rules = yaml.safe_load(yaml_content) #using safe_load to prevent exploits (thank you stack overflow)
                
                keys = [key for key in ["PROMPT_OVERRIDE", "PROMPT_PRE", "PROMPT_POST"] if key in rules]
            if keys:
                logger.debug(f"Loaded prompt rules: {', '.join(keys)}")
            else:
                logger.debug("No valid keys found.")

                return rules if rules is not None else {}
        except Exception as ex:
            logger.error(f"Error reading saist.rules: {ex}")
            return {}

#I first wrote this code in c# using dictionaries and a similar yaml parsing library for .net and then used a converter for python. 
#I'm not too well versed with python yet but doing this excersise and seeing how things are converted, learning some syntax and hacking stuff together has been a massive help and has been really enjoyable!

