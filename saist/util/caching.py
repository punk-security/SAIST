from scm import Scm
from models import Finding, FindingJSONEncoder
import hashlib
import json

async def hash_file(scm: Scm, filename: str) -> str:
    file: str = await scm.read_file_contents(filename)
    return hashlib.md5(file.encode()).hexdigest()

def finding_from_json_cache(json_dict: dict[str, any]) -> Finding:
    return Finding.model_validate(json_dict)

def findings_from_cache_file(cache_file: str) -> list[Finding]:
    with open(cache_file, 'r') as file:
        cache_json: dict[str, list[dict] | str] = json.load(file, object_hook=dict[str, list[dict] | str])
        return [finding_from_json_cache(json_dict) for json_dict in cache_json["findings"]]

def store_findings_to_cache_file(filename: str, findings: list[Finding], cache_file: str):
    cache_dict: dict[str, list[Finding] | str] = { 
            "path": filename,
            "findings": findings,
        }
    with open(cache_file, "w") as cf:
        json.dump(cache_dict, cf, cls=FindingJSONEncoder)