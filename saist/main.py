#!/usr/bin/env python3
import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from latex import Latex

from llm.adapters import BaseLlmAdapter
from llm.adapters.anthropic import AnthropicAdapter
from llm.adapters.bedrock import BedrockAdapter
from llm.adapters.deepseek import DeepseekAdapter
from llm.adapters.faike import FaikeAdapter
from llm.adapters.gemini import GeminiAdapter
from llm.adapters.ollama import OllamaAdapter
from llm.adapters.openai import OpenAiAdapter

from models import Finding, FindingContext, FindingEnriched, Findings

from scm import BaseScmAdapter, Scm
from scm.adapters.filesystem import FilesystemAdapter
from scm.adapters.git import GitAdapter
from scm.adapters.github import Github

from shell import Shell

from util.argparsing import parse_args
from util.caching import *
from util.filtering import FilterRules
from util.git import parse_unified_diff
from util.output import print_banner, write_csv
from util.poem import poem
from util.prompts import prompts

from web import FindingsServer

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.console import Group
from rich.live import Live

prompts = prompts()
load_dotenv(".env")

logger = logging.getLogger("saist")

async def analyze_single_file(scm: Scm, adapter: BaseLlmAdapter, filename, patch_text, disable_tools: bool) -> Optional[list[Finding]]:
    """
    Analyzes a SINGLE file diff with OpenAI, returning a Findings object or None on error.
    """
    system_prompt = prompts.DETECT
    logger.debug(f"Processing {filename}")
    prompt = (
        f"\n\nFile: {filename}\n{patch_text}\n"
    )
    try:
        return (await adapter.prompt_structured(system_prompt, prompt, Findings, [] if disable_tools else [scm.read_file_contents])).findings
    except Exception as e:
        logger.error(f"[Error] File '{filename}': {e}")
        return None

async def context_from_finding(scm: Scm, finding: Finding, context_size: int = 3) -> Optional[list]:
    """

    """
    try:
        file_contents = await scm.read_file_contents(finding.file)
    except Exception as e:
        logger.error(f"[Error] File '{finding.file}': {e}")
        return None

    start = max(1, finding.line_number - context_size)
    end = finding.line_number + context_size

    context = []
    lines = file_contents.split("\n")
    for ln in range(start, min(end + 1, len(lines) + 1)):
        context.append(lines[ln - 1])

    return "\n".join(context), start, end

def generate_summary_from_findings(adapter: BaseLlmAdapter, findings: list[Finding]) -> str:
    """
    Uses OpenAI to generate a summary of all findings to be used as the PR review body.
    """
    system_prompt = prompts.SUMMARY
    prompt = ""
    for f in findings:
        prompt += f"- **File**: `{f.file}`\n  - **Issue**: {f.issue}\n  - **Recommendation**: {f.recommendation}\n\n"

    try:
        return adapter.prompt(system_prompt, prompt)
    except Exception as e:
        logger.error(f"[Error generating summary] {e}")
        return "Security issues found. Please review the inline comments."

def _get_scm_adapter(args) -> BaseScmAdapter:
    if args.SCM == 'github':
        logger.debug("Using SCM: Github")
        return Github(
            github_token=args.github_token,
            repo = args.repository,
            pr_number=args.pr
        )

    if args.SCM == "git":
        logger.debug("Using SCM: Git")
        return GitAdapter(
            base_commit=args.commit_for_compare, 
            base_branch=args.ref_for_compare, 
            compare_branch=args.ref_to_compare, 
            compare_commit=args.commit_to_compare)

    if args.SCM  == "filesystem":
        logger.debug("Using SCM: Filesystem")
        return FilesystemAdapter(
            compare_path=args.path, 
            base_path=args.path_for_comparison)

    raise Exception("Could not determine a suitable file source")

async def _get_llm_adapter(args) -> BaseLlmAdapter:

    model = args.llm_model

    if args.llm == 'anthropic':
        llm = AnthropicAdapter( api_key = args.llm_api_key, model=model)
        logger.debug(f"Using LLM: anthropic Model: {llm.model_name}")
    elif args.llm == 'bedrock':
        llm = BedrockAdapter( api_key = args.llm_api_key, model=model)
        logger.debug(f"Using LLM: AWS bedrock Model: {llm.model_name}")
    elif args.llm == 'deepseek':
        llm = DeepseekAdapter(api_key = args.llm_api_key, model=model)
        logger.debug(f"Using LLM: deepseek Model: {llm.model_name}")
    elif args.llm ==  'openai':
        llm = OpenAiAdapter(api_key = args.llm_api_key, model=model)
        logger.debug(f"Using LLM: openai Model: {llm.model_name}")
    elif args.llm ==  'gemini':
        llm = GeminiAdapter(api_key = args.llm_api_key, model=model)
        logger.debug(f"Using LLM: gemini Model: {llm.model_name}")
    elif args.llm == 'ollama':
        llm = OllamaAdapter(api_key = args.llm_api_key, base_url=args.ollama_base_uri, model=model)
        await llm.initialize()
        logger.debug(f"Using LLM: ollama Model: {llm.model_name}")
    elif args.llm == 'faike':
        llm = FaikeAdapter("", "Fake LLM")
        logger.debug("Using LLM: Faike AI")
    else:
        raise Exception("Could not determine a suitable LLM to use")
    return llm

async def main():
    """
    Main flow:
      1. Get changed files (with diffs) from the PR.
      2. Filter only 'app code' files by extension and parse diffs.
      3. Send each file's diff to OpenAI *in parallel* using ThreadPoolExecutor.
      4. Collect all findings, then map each snippet back to the correct line & diff position.
      5. Post a single PR review with all combined findings.
    """
    print_banner()
    args = parse_args()

    log_level = logging.WARN
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose > 1:
        log_level = logging.DEBUG
    
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=log_level)

    print("🚀 Initializing LLM adapter...")
    llm = await _get_llm_adapter(args)
    print(f"✅ Using LLM: {args.llm} (Model: {llm.model_name})\n")

    if args.SCM == "poem":
        print("📝 Generating poem...\n")
        await poem(llm)
        print("✨ Poem generation completed.\n")
        exit(0)

    print("🔎 Initializing SCM adapter...")
    scm_adapter = _get_scm_adapter(args)
    scm = Scm(adapter=scm_adapter)
    print(f"✅ Using SCM: {args.SCM}\n")

    # 1) Get changed files
    print("📂 Fetching changed files...")
    changed_files = scm.get_changed_files()
    if not changed_files:
        print("⚠️ No changed files detected. Exiting.")
        return
    print(f"✅ Detected {len(changed_files)} changed files\n")

    # 2) Gather only relevant app code diffs
    print("🧹 Filtering relevant app code diffs...")
    file_line_maps = {}
    file_new_lines_text = {}
    app_files = []

    filter_rules = FilterRules(args.include, args.exclude)
    for f in changed_files:
        filename = f["filename"]
        patch_text = f.get("patch", "")
        if not patch_text:
            logging.debug(f"Skipped file {filename} as it contains no patch text")
            continue 

        if not filter_rules.filename_included(filename):
            logging.debug(f"Skipped file {filename} as it is not included in rules")
            continue

        if not args.skip_line_length_check:
            if filter_rules.file_exceeds_line_length_limit(file_content=await scm.read_file_contents(filename), patch_text=patch_text, max_line_length=args.max_line_length):
                logging.debug(f"Skipped file {filename} as it contains lines that exceed the maximum line length ({args.max_line_length})")
                continue

        line_map, new_lines_text = parse_unified_diff(patch_text)
        file_line_maps[filename] = line_map
        file_new_lines_text[filename] = new_lines_text
        app_files.append((filename, patch_text))

    if not app_files:
        print("⚠️ No app code diffs to analyze. Exiting.")
        return
    print(f"✅ Prepared {len(app_files)} app files for analysis.\n")

    app_filenames = list((filename for filename,_ in app_files))
    logging.debug(f"Files to process: {app_filenames}")

    if args.dry_run:
        print("⚠️  --dry-run flag passed, exiting without analyzing files.")
        exit(0)

    # 3) Analyze each file in parallel
    print("🔍 Analyzing files for security issues...")
    max_workers = min(args.llm_rate_limit, len(app_files))
    logging.debug(f"{max_workers=}")
    all_findings = await generate_findings(scm, llm, app_files, max_workers, args.disable_tools, args.disable_caching, args.cache_folder)

    if not all_findings:
        print("✅ No findings reported. Exiting.\n")
        return
    print(f"🚨 Analysis complete! Identified {len(all_findings)} potential issues.\n")

    # 4) Build review comments from snippet-based findings
    review_comments = []
    all_findings.sort(key=lambda x: x.priority,reverse=True)
    
    for item in all_findings:
        item.line_number = -1 #set to -1 for filtering. Gets changed later if finding is valid
        file_name = item.file
        snippet = item.snippet
        issue = item.issue
        priority = "LOW"
        if item.priority > 4:
            priority = "MEDIUM"
        if item.priority > 7:
            priority = "HIGH"
        if item.priority > 8:
            priority = "CRITICAL"
        cwe = item.cwe
        recommendation = item.recommendation

        # Basic checks
        if not file_name or not snippet or not issue:
            continue
        if file_name not in file_line_maps:
            # Possibly flagged a file that doesn't exist in the PR
            continue

        line_map = file_line_maps[file_name]
        new_lines_text = file_new_lines_text[file_name]

        # Attempt to find which 'new_line' has the snippet
        matched_new_line = None
        for ln, code_text in new_lines_text.items():
            if snippet in code_text:
                matched_new_line = ln
                break

        if not matched_new_line:
            # If we can't find the snippet in the patch, skip
            continue

        diff_position = line_map[matched_new_line]
        body_text = (
            f"**Security Issue:** {issue}\n\n"
            f"**Priority:** {priority}\n\n"
            f"**CWE:** {cwe}\n\n"
            f"**Recommendation:** {recommendation or 'None provided.'}\n\n"
            f"**Snippet**: `{snippet}`\n\n"
        )

        review_comments.append({
            "path": file_name,
            "position": diff_position - 1,
            "body": body_text
        })

        item.line_number = matched_new_line

    all_findings = list([x for x in all_findings if x.line_number != -1])

    if not all_findings:
        print("No issues detected")
        exit(0)

    if args.interactive:
        s = Shell(llm, scm, all_findings)
        await s.run()
        all_findings = s.findings


    comment = await generate_summary_from_findings(llm, all_findings)
    scm.create_review(
        comment=comment,
        review_comments=review_comments,
        request_changes=True
    )
    logger.debug("Review posted with snippet-based security annotations for all analyzed files.")

    if args.csv:
        write_csv(all_findings, args.csv_path)

    if args.web:
        enriched_findings = []
        for finding in all_findings:
            try:
                file_contents = await scm.read_file_contents(finding.file)
                ef = FindingEnriched.model_validate(
                {
                    **dict(finding),
                    "file_contents": file_contents
                }
                )
            except Exception as e:
                ef = FindingEnriched.model_validate(
                    {
                    **dict(finding),
                    "file_contents": "ERR: Could not retrieve contents"
                }
                )
            enriched_findings.append(ef)
        w = FindingsServer(args.web_host, args.web_port)
        w.run(enriched_findings)

    if args.pdf or args.tex:
        findings_context = []
        for finding in all_findings:
            try:
                context, start, end = await context_from_finding(scm, finding, 10)
                fc = FindingContext.model_validate(
                    {
                        **dict(finding),
                        "context": context,
                        "context_start": start,
                        "context_end": end,
                    }
                )
                findings_context.append(fc)
            except:
                continue
        l = Latex(llm, args.project_name, findings_context, comment)
        l.run(args)

    if args.ci and len(all_findings) > 0:
        exit(1)

async def process_file(scm: Scm, llm, filename, patch_text, disable_tools, disable_caching, cache_folder):
    start = asyncio.get_event_loop().time()
    if disable_caching is True: 
        result = await analyze_single_file(scm, llm, filename, patch_text, disable_tools)
    else:
        hash: str = await hash_file(scm, filename)
        cache_file = os.path.join(cache_folder, hash + ".json")
        if not os.path.exists(cache_file):
            result = await analyze_single_file(scm, llm, filename, patch_text, disable_tools)
            store_findings_to_cache_file(filename, result, cache_file)
        else:
            result = findings_from_cache_file(cache_file)
    elapsed = asyncio.get_event_loop().time() - start
    if elapsed < 1:
        await asyncio.sleep(1 - elapsed)

    return result

async def generate_findings(scm, llm, app_files, max_concurrent, disable_tools, disable_caching, cache_folder):
    if disable_caching is False:
        if not os.path.exists(cache_folder) or not os.path.isdir(cache_folder):
            os.makedirs(cache_folder, exist_ok=True)
    
    semaphore = asyncio.Semaphore(max_concurrent)

    overall_progress = Progress(
        TextColumn("[bold blue]{task.description}"), 
        BarColumn(), 
        MofNCompleteColumn(), 
        TimeElapsedColumn(), 
        TimeRemainingColumn())
    
    file_progress = Progress(
        SpinnerColumn(),
        TextColumn("[blue]{task.description}"),
        transient=True
    )

    progress_group = Group(
        overall_progress,
        file_progress,
    )

    def task_progress_wrapper(func, overall_progress, overall_task, file_progress, filename, semaphore):
        async def sub_func(*args, **kwargs):
            async with semaphore:
                task_description_text = f"{filename}..."
                file_task = file_progress.add_task(description=task_description_text, transient=True)
                task_result = await func(*args, **kwargs)
                file_progress.remove_task(file_task)
                file_progress.refresh()
                overall_progress.update(overall_task, advance=1)
                return task_result
        return sub_func
    

    with Live(progress_group):
        tasks = []
        overall_task = overall_progress.add_task(f"Analyzing {len(app_files)} files...", total=len(app_files), start=True) # Add a task
        for filename, patch_text in app_files:
            wrapper_func = task_progress_wrapper(process_file, overall_progress, overall_task, file_progress, filename, semaphore)(scm, llm, filename, patch_text, disable_tools, disable_caching, cache_folder)
            tasks.append(
                wrapper_func
            )

        all_findings = []
        try:
            results = await asyncio.gather(*tasks)
        finally:
            overall_progress.stop()
            file_progress.stop()

    for result in results:
        if result:
            all_findings.extend(result)

    return all_findings

if __name__ == "__main__":
    asyncio.run(main())
