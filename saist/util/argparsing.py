import argparse
from os import linesep, environ, cpu_count
import sys
from shutil import which
from dotenv import load_dotenv

load_dotenv(".env")

runtime = environ.get("SAIST_COMMAND", f"{sys.argv[0]}")

banner = r"""
          ____              __   _____                      _ __       
         / __ \__  ______  / /__/ ___/___  _______  _______(_) /___  __
        / /_/ / / / / __ \/ //_/\__ \/ _ \/ ___/ / / / ___/ / __/ / / /
       / ____/ /_/ / / / / ,<  ___/ /  __/ /__/ /_/ / /  / / /_/ /_/ / 
      /_/    \__,_/_/ /_/_/|_|/____/\___/\___/\__,_/_/  /_/\__/\__, /  
                                             PRESENTS         /____/  
                    SAIST -> Static AI-powered Scanning Tool 
                        🪄 Scan literally anything with ✨ AI ✨
        """


class CustomParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stdout.write(f" ❌ error: {message}{linesep}{linesep}")
        self.print_usage()
        sys.exit(2)

parser = CustomParser(
    usage=f"{linesep} {runtime} [options] {{ filesystem / git / github / poem }} {linesep}",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=f"""

Tips:{linesep}
> Set your LLM API key with SAIST_LLM_API_KEY env var to keep it out your bash history
... otherwise provide it with --llm-api-key <key> {linesep}
Examples:{linesep}
> Get a poem from your favourite LLM
{runtime} --llm <llm> poem{linesep}
> Scan local code folder with deepseek
{runtime} --llm deepseek filesystem <path>{linesep}
> Scan local code folder with deepseek and get csv output
{runtime} --llm deepseek --csv filesystem <path>{linesep}
> Scan local git repo with openai and specific model
{runtime} --llm openai --llm-model gpt4o git <path>{linesep}
> Scan local code folder with ollama and get interactive shell
{runtime} --llm ollama --interactive filesystem <path>{linesep}
> Scan local code folder with anthropic and get web server findings
{runtime} --llm anthropic --interactive filesystem <path>{linesep}
{linesep}
""",
)

class EnvDefault(argparse.Action):
    def __init__(self, envvar, required=True, default=None, **kwargs):
        if envvar:
            if envvar in environ:
                default = environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required, 
                                         **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)

SCM_subparsers = parser.add_subparsers(dest="SCM", help='SCM choice',required=True)

filesystem_parser = SCM_subparsers.add_parser("poem", help = "Forget code scanning, get a nice little DevSecOps poem")

### FILESYTEM
filesystem_parser = SCM_subparsers.add_parser("filesystem", help = "Scan a local folder on disk")
filesystem_parser.add_argument(
    "path", type=str, help="Path to the folder to be scanned",
    envvar="SAIST_FILESYSTEM_PATH", action=EnvDefault
    )
filesystem_parser.add_argument(
    "--path-for-comparison", type=str, help = "Path to generate diff with",
    envvar="SAIST_COMPARE_PATH", action=EnvDefault, required=False
    )


### GIT 
git_parser = SCM_subparsers.add_parser("git", help = "Scan a local git repository on disk")
git_parser.add_argument(
    "path", type=str, help="Path to the folder to be scanned",
    envvar="SAIST_FILESYSTEM_PATH", action=EnvDefault
    )
git_parser.add_argument(
    "--ref-for-compare", type=str, help = "Git ref to compare from",
    envvar="SAIST_GIT_BASE_REF", action=EnvDefault, default="main"
    )
git_parser.add_argument("--ref-to-compare", type=str, help = "Git ref to compare to",
    envvar="SAIST_GIT_COMPARE_REF", action=EnvDefault, default="HEAD"
    )
git_parser.add_argument(
    "--commit-for-compare", type=str, help = "Git commit to compare from (preferred over REF if set)",
    envvar="SAIST_GIT_BASE_COMMIT", action=EnvDefault
    )
git_parser.add_argument("--commit-to-compare", type=str, help = "Git commit to compare to (preferred over REF if set)",
    envvar="SAIST_GIT_COMPARE_COMMIT", action=EnvDefault
    )

### GITHUB
github_parser = SCM_subparsers.add_parser("github", help = "Scan a github PR")
github_parser.add_argument(
    "repository", type=str, help="Repository",
    envvar="GITHUB_REPOSITORY", action=EnvDefault
    )
github_parser.add_argument(
    "--github-token", type=str, help = "Github API token (can be set with env var GITHUB_TOKEN)",
    envvar="GITHUB_TOKEN", action=EnvDefault, required=True
    )
github_parser.add_argument(
    "pr", type=str, help = "Pull Request ID",
    envvar="PR_NUMBER", action=EnvDefault
    )

parser.add_argument(
    "--llm",
    type=str,
    choices=["anthropic", "bedrock", "deepseek", "gemini", "ollama", "openai", "faike"],
    required=True,
    action=EnvDefault,
    envvar="SAIST_LLM"
)

parser.add_argument(
    "--llm-api-key", type=str, help = "API key for LLM (can be set with env var SAIST_LLM_API_KEY)",
    envvar="SAIST_LLM_API_KEY", action=EnvDefault, required=False
    )

parser.add_argument(
    "--llm-model", type=str, help = "LLM model to use, othwerise use the default",
    envvar="SAIST_LLM_MODEL", action=EnvDefault, required=False
    )

parser.add_argument(
    "--llm-rate-limit", help = "Max requests per second", envvar="SAIST_LLM_RATE_LIMIT", 
    action=EnvDefault, required=False, type=int, default = 10
    )

parser.add_argument(
    "--ollama-base-uri", type=str, help = "Base uri of ollama",
    envvar="SAIST_OLLAMA_BASE_URI", action=EnvDefault, default = "http://localhost:11434"
    )

parser.add_argument(
    "--openai-base-uri", type=str, help = "Base uri of openai to use any compatable service",
    envvar="SAIST_OPENAI_BASE_URI", action=EnvDefault, required=False
    )

parser.add_argument(
    "--interactive", help = "Spawn an interactive prompt with the LLM at the end",
    required=False, action='store_true'
    )

parser.add_argument(
    "--disable-tools", help="Disable usage of tools during code analysis (this is a good cost saving)",
    required=False, action="store_true"
    )

parser.add_argument(
    "--web", help = "Launch a web server to display findings",
    required=False, action='store_true'
    )

parser.add_argument(
    "--web-port", help = "Port for web server to listen on", required=False, type=int, default = 8080
    )

parser.add_argument(
    "--web-host", type=str, help = "Host for the web server to bind to",
    envvar="SAIST_WEB_HOST", action=EnvDefault, default = "127.0.0.1"
    )


parser.add_argument(
    "--ci", help = "Exit 1 if findings identified", 
    required=False, action='store_true', 
    )

parser.add_argument(
    "--csv", help = "Write results to findings.csv", 
    required=False, action='store_true', 
    )

parser.add_argument(
    "--csv-path", type=str, help = "Path to write CSV results",
    envvar="SAIST_CSV_PATH", action=EnvDefault, required=False, default="results.csv"
    )

parser.add_argument(
    "--tex", help = "Write results of TeX file",
    required=False, action='store_true'
    )

parser.add_argument(
    "--tex-filename", type=str, help = "Filename of TeX file",
    envvar="SAIST_TEX_FILENAME", action=EnvDefault, required=False, default="report.tex"
    )

parser.add_argument(
    "--pdf", help = "Write results of PDF report",
    required=False, action='store_true'
    )

parser.add_argument(
    "--pdf-filename", type=str, help = "Filename of PDF report",
    envvar="SAIST_PDF_FILENAME", action=EnvDefault, required=False, default="report.pdf"
    )

parser.add_argument(
    "--disable-caching", help = "Disable local caching of results",
      action='store_true', required=False
    )

parser.add_argument(
    "--cache-folder", type=str, help = "Folder name for local caching",
    envvar="SAIST_CACHE_FOLDER", action=EnvDefault, required=False, default="SAISTCache"
    )

parser.add_argument(
    "--project-name", type=str, help = "Project name for pdf output",
    envvar="SAIST_PROJECT_NAME", action=EnvDefault, required=False, default=None
    )

parser.add_argument(
    "--skip-line-length-check", help = "Skip checking files for a maximum line length",
    action='store_true', required=False
    )

parser.add_argument(
    "--max-line-length", type=int, help = "Maximum allowed line length, files with lines longer than this value will be skipped",
    required=False, default=1000
    )

parser.add_argument(
    "-v",
    "--verbose",
    action="count",
    default=0,
    help="-v for verbose, -vv for extra verbose",
)

def parse_args():
    args = parser.parse_args()

    if args.llm == "bedrock" and args.llm_api_key:
        parser.error(f"Do not provide an API key for bedrock, use AWS ENV variables https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-envvars.html")

    if args.llm == "bedrock" and args.interactive:
        parser.error("Sorry, we dont support interactive mode with bedrock as AWS tool calling is a bit broken")

    if args.llm not in [ "ollama", "bedrock", "faike" ] and args.llm_api_key is None:
        parser.error(f"You must provide an api key with --llm-api-key if using {args.llm}")

    if args.llm == "ollama" and args.interactive:
        parser.error(f"You cannot use the interactive shell with ollama currently")

    if args.llm == "faike" and args.interactive:
        parser.error("Faike LLM: Certified non-existent AI doesn't support interactive mode")
   
    if args.pdf and which("latexmk") == None:
        parser.error("Unable to find 'latexmk' binary in $PATH needed for PDF report building, cannot use --pdf flag")

    return args
