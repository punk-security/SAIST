import os
import yaml

class PromptRules:
    RulesFile = "saist.rules"

    @staticmethod
    def apply_rules(prompt):
        rules = PromptRules.load_rules()

        override_prompt = rules.get("PROMPT_OVERRIDE")
        if override_prompt:
            #skip pre and post if override is present
            return override_prompt

        pre = rules.get("PROMPT_PRE", "")
        post = rules.get("PROMPT_POST", "")

        #add pre/post if they are present
        return f"{pre}{prompt}{post}"

    @staticmethod
    def load_rules():
        if not os.path.exists(PromptRules.RulesFile):
            print("No saist.rules file found.")
            return {} #return empty rules

        try:
            with open(PromptRules.RulesFile, 'r') as file:
                yaml_content = file.read()
                rules = yaml.safe_load(yaml_content) #using safe_load to prevent exploits (thank you stack overflow)
                return rules if rules is not None else {}
        except Exception as ex:
            print("Error reading saist.rules: " + str(ex))
            return {}

#I first wrote this code in c# using dictionaries and a similar yaml parsing library for .net and then used a converter for python. 
#I'm not too well versed with python yet but doing this excersise and seeing how things are converted, learning some syntax and hacking stuff together has been a massive help and has been really enjoyable!

