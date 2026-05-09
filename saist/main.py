#!/usr/bin/env python3
import asyncio
import logging
import os
from typing import Callable, Optional

from dotenv import load_dotenv
from reportlab_pdf import ReportLabPdf

from llm.adapters import BaseLlmAdapter
from llm.adapters.anthropic import AnthropicAdapter
from llm.adapters.azure_foundry import AzureFoundryAdapter
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
from util.skills import (
    format_analysis_skills,
    generate_skill_files,
    load_analysis_skills,
    project_root_from_args,
    resolve_skills_dir,
    skills_prompt_digest,
)

from web import FindingsServer

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.console import Group
from rich.live import Live

prompts = prompts()
load_dotenv(".env")

logger = logging.getLogger("saist")


class CoverageTrackingScm:
    def __init__(self, scm: Scm):
        self.scm = scm
        self.files_read: set[str] = set()

    async def read_file_contents(self, filename: str):
        contents = await self.scm.read_file_contents(filename)
        if contents is not None:
            self.files_read.add(filename)
        return contents

    async def list_files(self) -> list[str]:
        return await self.scm.list_files()

    async def regex_search(
        self,
        pattern: str,
        file_pattern: str = "**/*",
        max_results: int = 100,
    ) -> list[dict[str, str | int]]:
        results = await self.scm.regex_search(pattern, file_pattern, max_results)
        for result in results:
            filename = result.get("filename") if isinstance(result, dict) else None
            if filename:
                self.files_read.add(str(filename))
        return results

    def tool_functions(self) -> list[Callable]:
        return [self.read_file_contents, self.list_files, self.regex_search]


def scm_detect_prompt(scm: Scm) -> str:
    return scm.detect_prompt() if hasattr(scm, "detect_prompt") else FilesystemAdapter.DETECT_PROMPT


def scm_summary_prompt(scm: Scm) -> str:
    return scm.summary_prompt() if hasattr(scm, "summary_prompt") else FilesystemAdapter.SUMMARY_PROMPT

async def analyze_single_file(scm: Scm, adapter: BaseLlmAdapter, filename, patch_text, disable_tools: bool, analysis_skills: str = "") -> Optional[list[Finding]]:
    """
    Analyzes a SINGLE file diff with OpenAI, returning a Findings object or None on error.
    """
    system_prompt = prompts.detect(scm_detect_prompt(scm))
    if analysis_skills:
        system_prompt = f"{system_prompt}\n\n{analysis_skills}"

    logger.debug(f"Processing {filename}")
    prompt = (
        f"\n\nFile: {filename}\n{patch_text}\n"
    )
    try:
        return (await adapter.prompt_structured(system_prompt, prompt, Findings, [] if disable_tools else scm.tool_functions())).findings
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

def generate_summary_from_findings(adapter: BaseLlmAdapter, findings: list[Finding], scm_prompt: str = "") -> str:
    """
    Uses OpenAI to generate a summary of all findings to be used as the PR review body.
    """
    system_prompt = prompts.summary(scm_prompt)
    prompt = ""
    for f in findings:
        validation_steps = "\n".join(f"    - {step}" for step in f.validation_steps) or "    - Not provided"
        prompt += (
            f"- **File**: `{f.file}`\n"
            f"  - **Issue**: {f.issue}\n"
            f"  - **Recommendation**: {f.recommendation}\n"
            f"  - **Validation steps**:\n{validation_steps}\n\n"
        )

    try:
        return adapter.prompt(system_prompt, prompt)
    except Exception as e:
        logger.error(f"[Error generating summary] {e}")
        return "Security issues found. Please review the inline comments."


def build_finding_review_body(finding: Finding) -> str:
    priority = "LOW"
    if finding.priority > 4:
        priority = "MEDIUM"
    if finding.priority > 7:
        priority = "HIGH"
    if finding.priority > 8:
        priority = "CRITICAL"

    return (
        f"**Security Issue:** {finding.issue}\n\n"
        f"**Priority:** {priority}\n\n"
        f"**CWE:** {finding.cwe}\n\n"
        f"**Recommendation:** {finding.recommendation or 'None provided.'}\n\n"
        f"**Validation Steps:**\n{format_validation_steps(finding.validation_steps)}\n\n"
        f"**Snippet**: `{finding.snippet}`\n\n"
    )


def format_validation_steps(validation_steps: list[str]) -> str:
    if not validation_steps:
        return "None provided."
    return "\n".join(f"{index}. {step}" for index, step in enumerate(validation_steps, start=1))


def build_filesystem_review_comments(findings: list[Finding]) -> list[dict]:
    comments = []
    for finding in findings:
        if not finding.file or not finding.snippet or not finding.issue:
            continue
        comments.append(
            {
                "path": finding.file,
                "position": max(1, finding.line_number),
                "body": build_finding_review_body(finding),
            }
        )
    return comments


def build_diff_review_comments(findings: list[Finding], file_line_maps: dict) -> list[dict]:
    comments = []
    for finding in findings:
        diff_position = file_line_maps[finding.file][finding.line_number]
        comments.append(
            {
                "path": finding.file,
                "position": diff_position - 1,
                "body": build_finding_review_body(finding),
            }
        )
    return comments


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    deduped: dict[tuple[str, int, str], Finding] = {}
    order: list[tuple[str, int, str]] = []

    for finding in findings:
        key = (finding.file, finding.line_number, finding.cwe)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = finding
            order.append(key)
            continue

        if finding.priority > existing.priority:
            deduped[key] = finding

    return [deduped[key] for key in order]


async def generate_findings_with_filesystem_tools(
    scm: Scm,
    llm: BaseLlmAdapter,
    filenames: list[str],
    disable_tools: bool,
    analysis_skills: str = "",
) -> tuple[list[Finding], set[str]]:
    tracked_scm = CoverageTrackingScm(scm)
    system_prompt = prompts.detect(scm_detect_prompt(scm))
    if analysis_skills:
        system_prompt = f"{system_prompt}\n\n{analysis_skills}"

    file_list = "\n".join(f"- {filename}" for filename in filenames)
    user_prompt = f"""
Application file inventory:
{file_list}

Perform a penetration test style application security review of this codebase.
Use the available tools to inspect files before reporting findings.
Return only findings that are supported by code you inspected.
"""

    result = await llm.prompt_structured(
        system_prompt,
        user_prompt,
        Findings,
        [] if disable_tools else tracked_scm.tool_functions(),
    )
    return result.findings, tracked_scm.files_read


async def generate_findings_with_filesystem_tools_iterations(
    scm: Scm,
    llm: BaseLlmAdapter,
    filenames: list[str],
    disable_tools: bool,
    analysis_skills: str,
    iterations: int,
    max_concurrent: int,
) -> tuple[list[Finding], set[str]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrent))

    overall_progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    iteration_progress = Progress(
        SpinnerColumn(),
        TextColumn("[blue]{task.description}"),
        transient=True,
    )

    progress_group = Group(
        overall_progress,
        iteration_progress,
    )

    async def run_iteration(iteration: int, overall_task):
        async with semaphore:
            iteration_task = iteration_progress.add_task(
                description=f"Iteration {iteration}/{iterations}...",
                transient=True,
            )
            try:
                return await generate_findings_with_filesystem_tools(
                    scm=scm,
                    llm=llm,
                    filenames=filenames,
                    disable_tools=disable_tools,
                    analysis_skills=analysis_skills,
                )
            finally:
                iteration_progress.remove_task(iteration_task)
                iteration_progress.refresh()
                overall_progress.update(overall_task, advance=1)

    with Live(progress_group):
        overall_task = overall_progress.add_task(
            f"Running {iterations} tool-driven analysis iteration{'s' if iterations != 1 else ''}...",
            total=iterations,
            start=True,
        )
        try:
            results = await asyncio.gather(*(run_iteration(iteration, overall_task) for iteration in range(1, iterations + 1)))
        finally:
            overall_progress.stop()
            iteration_progress.stop()

    all_findings = []
    files_read = set()
    for findings, iteration_files_read in results:
        all_findings.extend(findings)
        files_read.update(iteration_files_read)

    return all_findings, files_read


def print_coverage(files_read: set[str], files_in_scope: list[str]):
    total = len(files_in_scope)
    read_count = len(files_read.intersection(files_in_scope))
    percent = (read_count / total * 100) if total else 0
    print(f"📈 LLM file coverage: {read_count}/{total} files read ({percent:.1f}%)\n")

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
    thinking = args.thinking

    if args.llm == 'anthropic':
        llm = AnthropicAdapter(api_key=args.llm_api_key, model=model, thinking=thinking)
        logger.debug(f"Using LLM: anthropic Model: {llm.model_name}")
    elif args.llm == 'azure-foundry':
        llm = AzureFoundryAdapter(
            api_key=args.llm_api_key,
            model=model,
            azure_endpoint=args.azure_openai_endpoint,
            api_version=args.azure_openai_api_version,
            thinking=thinking,
        )
        logger.debug(f"Using LLM: Azure AI Foundry Model: {llm.model_name}")
    elif args.llm == 'bedrock':
        llm = BedrockAdapter(api_key=args.llm_api_key, model=model, thinking=thinking)
        logger.debug(f"Using LLM: AWS bedrock Model: {llm.model_name}")
    elif args.llm == 'deepseek':
        llm = DeepseekAdapter(api_key=args.llm_api_key, model=model, thinking=thinking)
        logger.debug(f"Using LLM: deepseek Model: {llm.model_name}")
    elif args.llm ==  'openai':
        llm = OpenAiAdapter(api_key=args.llm_api_key, model=model, thinking=thinking)
        logger.debug(f"Using LLM: openai Model: {llm.model_name}")
    elif args.llm ==  'gemini':
        llm = GeminiAdapter(api_key=args.llm_api_key, model=model, thinking=thinking)
        logger.debug(f"Using LLM: gemini Model: {llm.model_name}")
    elif args.llm == 'ollama':
        llm = OllamaAdapter(api_key=args.llm_api_key, base_url=args.ollama_base_uri, model=model, thinking=thinking)
        await llm.initialize()
        logger.debug(f"Using LLM: ollama Model: {llm.model_name}")
    elif args.llm == 'faike':
        llm = FaikeAdapter("", "Fake LLM", thinking=thinking)
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

    project_root = project_root_from_args(args)
    skills_dir = resolve_skills_dir(project_root, args.skills_path)

    if args.generate_skills:
        print("🧭 Generating SAIST analysis skills...")
        result = await generate_skill_files(
            llm=llm,
            project_root=project_root,
            skills_dir=skills_dir,
            max_files=args.skills_sample_files,
            max_file_bytes=args.skills_sample_bytes,
            overwrite=args.overwrite_skills,
        )
        print(f"✅ Sampled {result.sampled_files} files from {project_root}")
        print(f"✅ Wrote {len(result.written)} skill files to {result.skills_dir}")
        if result.skipped:
            print(f"ℹ️ Skipped {len(result.skipped)} existing skill files. Use --overwrite-skills to replace them.")
        return

    print("🔎 Initializing SCM adapter...")
    scm_adapter = _get_scm_adapter(args)
    scm = Scm(adapter=scm_adapter)
    print(f"✅ Using SCM: {args.SCM}\n")

    shallow_filesystem_scan = args.SCM == "filesystem" and not args.deep
    analysis_skills = ""
    if not args.disable_skills:
        loaded_skills = load_analysis_skills(skills_dir, args.skills_max_bytes)
        if shallow_filesystem_scan and not loaded_skills:
            print("🧭 No SAIST skill files found. Generating application skills for this filesystem scan...")
            result = await generate_skill_files(
                llm=llm,
                project_root=project_root,
                skills_dir=skills_dir,
                max_files=args.skills_sample_files,
                max_file_bytes=args.skills_sample_bytes,
                overwrite=False,
            )
            print(f"✅ Sampled {result.sampled_files} files from {project_root}")
            print(f"✅ Wrote {len(result.written)} skill files to {result.skills_dir}")
            if result.skipped:
                print(f"ℹ️ Skipped {len(result.skipped)} existing skill files.")
            loaded_skills = load_analysis_skills(skills_dir, args.skills_max_bytes)

        if loaded_skills:
            analysis_skills = format_analysis_skills(loaded_skills)
            print(f"🧠 Loaded {len(loaded_skills)} SAIST skill files from {skills_dir}\n")
        else:
            logging.debug(f"No SAIST skill files found under {skills_dir}")
    else:
        logging.debug("SAIST skill loading disabled")

    filter_rules = FilterRules(args.include, args.exclude)
    review_comments = []

    if shallow_filesystem_scan:
        print("📂 Listing application files...")
        all_files = await scm.list_files()
        app_filenames = [filename for filename in all_files if filter_rules.filename_included(filename)]

        if not app_filenames:
            print("⚠️ No app files to analyze. Exiting.")
            return

        print(f"✅ Prepared {len(app_filenames)} app files for tool-driven analysis.\n")

        if args.dry_run:
            print("⚠️  --dry-run flag passed, exiting without analyzing files.")
            exit(0)

        print(f"🔍 Analyzing application with LLM tool use ({args.iterations} iteration{'s' if args.iterations != 1 else ''})...")
        all_findings, files_read = await generate_findings_with_filesystem_tools_iterations(
            scm=scm,
            llm=llm,
            filenames=app_filenames,
            disable_tools=args.disable_tools,
            analysis_skills=analysis_skills,
            iterations=args.iterations,
            max_concurrent=args.llm_rate_limit,
        )
        print_coverage(files_read, app_filenames)

        if not all_findings:
            print("✅ No findings reported. Exiting.\n")
            return

    else:

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
        all_findings = await generate_findings(scm, llm, app_files, max_workers, args.disable_tools, args.disable_caching, args.cache_folder, analysis_skills)

        if not all_findings:
            print("✅ No findings reported. Exiting.\n")
            return

        # 4) Build review comments from snippet-based findings
        all_findings.sort(key=lambda x: x.priority,reverse=True)
        
        for item in all_findings:
            item.line_number = -1 #set to -1 for filtering. Gets changed later if finding is valid
            file_name = item.file
            snippet = item.snippet
            issue = item.issue

            # Basic checks
            if not file_name or not snippet or not issue:
                continue
            if file_name not in file_line_maps:
                # Possibly flagged a file that doesn't exist in the PR
                continue

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

            item.line_number = matched_new_line

        all_findings = list([x for x in all_findings if x.line_number != -1])


    all_findings = dedupe_findings(all_findings)
    all_findings.sort(key=lambda x: x.priority, reverse=True)

    if not all_findings:
        print("No issues detected")
        exit(0)

    print(f"🚨 Analysis complete! Identified {len(all_findings)} potential issues.\n")

    if shallow_filesystem_scan:
        review_comments = build_filesystem_review_comments(all_findings)
    else:
        review_comments = build_diff_review_comments(all_findings, file_line_maps)

    if args.interactive:
        s = Shell(llm, scm, all_findings)
        await s.run()
        all_findings = s.findings


    comment = await generate_summary_from_findings(llm, all_findings, scm_summary_prompt(scm))
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

    if args.pdf:
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
        r = ReportLabPdf(llm, args.project_name, findings_context, comment)
        r.run(args)

    if args.ci and len(all_findings) > 0:
        exit(1)

async def process_file(scm: Scm, llm, filename, patch_text, disable_tools, disable_caching, cache_folder, analysis_skills):
    start = asyncio.get_event_loop().time()
    if disable_caching is True: 
        result = await analyze_single_file(scm, llm, filename, patch_text, disable_tools, analysis_skills)
    else:
        hash: str = await hash_file(scm, filename)
        cache_filename = hash + ".json"
        if analysis_skills:
            cache_filename = hash + "-" + skills_prompt_digest(analysis_skills) + ".json"

        cache_file = os.path.join(cache_folder, cache_filename)
        if not os.path.exists(cache_file):
            result = await analyze_single_file(scm, llm, filename, patch_text, disable_tools, analysis_skills)
            store_findings_to_cache_file(filename, result, cache_file)
        else:
            result = findings_from_cache_file(cache_file)
    elapsed = asyncio.get_event_loop().time() - start
    if elapsed < 1:
        await asyncio.sleep(1 - elapsed)

    return result

async def generate_findings(scm, llm, app_files, max_concurrent, disable_tools, disable_caching, cache_folder, analysis_skills):
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
            wrapper_func = task_progress_wrapper(process_file, overall_progress, overall_task, file_progress, filename, semaphore)(scm, llm, filename, patch_text, disable_tools, disable_caching, cache_folder, analysis_skills)
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
