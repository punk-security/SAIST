from scm import Scm
from models import Finding, FindingJSONEncoder
import hashlib
import json

async def hash_file(scm: Scm, filename: str) -> str:
    file: str = await scm.read_file_contents(filename)
    return hashlib.sha256(file.encode()).hexdigest()

async def hash_files(scm: Scm, filenames: list[str], extra: str = "") -> str:
    hasher = hashlib.sha256()
    if extra:
        hasher.update(extra.encode("utf-8"))
        hasher.update(b"\0")

    for filename in sorted(filenames):
        hasher.update(filename.encode("utf-8"))
        hasher.update(b"\0")
        file_contents = await scm.read_file_contents(filename)
        if file_contents is None:
            hasher.update(b"<SAIST:UNREADABLE>")
        else:
            hasher.update(file_contents.encode("utf-8"))
        hasher.update(b"\0")

    return hasher.hexdigest()

def finding_from_json_cache(json_dict: dict[str, any]) -> Finding:
    return Finding.model_validate(json_dict)

def findings_from_cache_file(cache_file: str) -> list[Finding]:
    with open(cache_file, 'r', encoding="utf-8") as file:
        cache_json: dict[str, list[dict] | str] = json.load(file, object_hook=dict[str, list[dict] | str])
        if cache_json["findings"] is not None: 
            return [finding_from_json_cache(json_dict) for json_dict in cache_json["findings"]]
    return []

def store_findings_to_cache_file(filename: str, findings: list[Finding], cache_file: str):
    cache_dict: dict[str, list[Finding] | str] = { 
            "path": filename,
            "findings": findings,
        }
    with open(cache_file, "w", encoding="utf-8") as cf:
        json.dump(cache_dict, cf, cls=FindingJSONEncoder)

def filesystem_tool_findings_from_cache_file(cache_file: str) -> tuple[list[Finding], set[str]]:
    with open(cache_file, "r", encoding="utf-8") as file:
        cache_json = json.load(file)
        findings = cache_json.get("findings") or []
        files_read = cache_json.get("files_read") or []
        return [finding_from_json_cache(json_dict) for json_dict in findings], set(files_read)

def store_filesystem_tool_findings_to_cache_file(
    iteration: int,
    filenames: list[str],
    findings: list[Finding],
    files_read: set[str],
    cache_file: str,
):
    cache_dict = {
        "path": f"filesystem-tool-iteration-{iteration}",
        "files": sorted(filenames),
        "files_read": sorted(files_read),
        "findings": findings,
    }
    with open(cache_file, "w", encoding="utf-8") as cf:
        json.dump(cache_dict, cf, cls=FindingJSONEncoder)
