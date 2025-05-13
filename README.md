[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://GitHub.com/punk-security/saist/graphs/commit-activity)
[![Maintainer](https://img.shields.io/badge/maintainer-PunkSecurity-blue)](https://www.punksecurity.co.uk)
[![Docker Pulls](https://img.shields.io/docker/pulls/punksecurity/saist)](https://hub.docker.com/r/punksecurity/dnsreaper)

# 🪄 SAIST - Static AI-powered Scanning Tool

**Scan anything with ✨ AI ✨ — spot vulnerabilities fast.**

---

## 🚀 About

**SAIST** (Static AI-powered Scanning Tool) is an open-source project that scans codebases for vulnerabilities using **AI**.  
It supports multiple LLMs, and can scan **full codebases**, **diffs between commits**, or even **GitHub PRs** automatically.

> Bonus: It can even generate DevSecOps poems if you're feeling whimsical. 🎤

Lots of vendors are rushing to charge a crazy amount of money to simply throw your code through ChatGPT. 

Well, now you can cut out the middle man and scan them yourself using SAIST (and choose whichever LLM you like).

We support OLLAMA for local / offline code scanning.

---

## ✨ Features

- **AI-powered vulnerability scanning** for entire codebases
- **Diff scanning**: Git commits, branches, or PRs
- **Multi-LLM support**: `OpenAI`, `Anthropic`, `Bedrock`, `DeepSeek`, `Gemini`, `Ollama`
- **Filesystem, Git, GitHub PR scanning modes**
- **Pattern-based file inclusion/exclusion** using `.saist.include` and `.saist.ignore`
- **Interactive chat** with your findings
- **Web server** UI to view results
- **CSV export** of findings
- **CI/CD pipeline friendly** (exit 1 on findings)

---

## 🛠️ Installation

### Run direct
```bash
git clone https://github.com/yourname/saist.git
cd saist
pip install -r requirements.txt
```

### Run via docker
```bash
docker pull punksecurity/saist
```
---

## 📦 Usage

```bash
saist/main.py --llm <llm_provider> [options] {filesystem | git | github | poem}
# or via docker
docker run punksecurity/saist --llm <llm_provider> [options] {filesystem | git | github | poem}
```

Set your LLM API key with environment variable:

```bash
export SAIST_LLM_API_KEY=your-api-key
```

---

## ⚡ Examples

| Task | Command |
|:-----|:--------|
| Get a DevSecOps poem | `saist/main.py --llm openai poem` |
| Scan a local folder | `saist/main.py --llm deepseek filesystem /path/to/code` |
| Scan a local Git repo | `saist/main.py --llm openai git /path/to/repo` |
| Scan a local Git repo (branch diff) | `saist/main.py --llm openai git /path/to/repo --ref-for-compare main --ref-to-compare feature-branch` |
| Scan a GitHub PR (and update the PR) | `saist/main.py --llm anthropic github yourorg/yourrepo 1234 --github-token your-token` |
| Launch web server to view findings | `saist/main.py --llm deepseek --web filesystem /path/to/code` |
| Interactive shell after scanning | `saist/main.py --llm ollama --interactive filesystem /path/to/code` |
| Export findings as CSV | `saist/main.py --llm openai --csv filesystem /path/to/code` |

---

## 🗂️ File Filtering

saist respects **file include/exclude rules** via two optional files in the root of the project:

| File              | Purpose                            |
| ----------------- | ---------------------------------- |
| `saist.include`    | List of glob patterns to **include** |
| `saist.ignore`     | List of glob patterns to **ignore** |

- Patterns follow `glob` syntax (similar to `.gitignore`).
- If **`saist.include`** does not exist, default extensions are used (e.g., `.py`, `.js`, `.java`, `.go`, etc).
- Examples:
    - `**/*.py` includes all Python files
    - `src/**/*.ts` includes TypeScript files inside `src`
    - `tests/**` in `saist.ignore` will ignore the entire tests folder

> Note: saist currently does basic glob pattern matching. More advanced `.gitignore`-style support is coming soon!

---

### 📝 Example

`saist.include`
```
**/*.py
**/*.ts
src/**/*.js
```

`saist.ignore`
```
tests/**
docs/**
```

This setup will:
- Only scan `.py`, `.ts`, and specific `.js` files
- Ignore anything under `tests/` and `docs/`

---

## ⚙️ Command Options

| Option | Description |
|:------|:------------|
| `--llm` | Select LLM (`anthropic`, `deepseek`, `gemini`, `ollama`, `openai`) |
| `--llm-api-key` | API key for your LLM |
| `--llm-model` | (Optional) Specific model (e.g., `gpt-4o`) |
| `--interactive` | Chat with the LLM after scan |
| `--web` | Launch a local web server |
| `--csv` | Output findings to `findings.csv` |
| `--ci` | Exit with code 1 if vulnerabilities found |
| `-v, --verbose` | Increase output verbosity |
| _Git-specific:_ |
| `--ref-for-compare` / `--ref-to-compare` | Compare Git refs |
| `--commit-for-compare` / `--commit-to-compare` | Compare Git commits |
| _GitHub-specific:_ |
| `--github-token` | GitHub token |
| `repository` / `pr` | Repo and Pull Request ID |

---

## 🧩 Architecture

- Pluggable SCM adapters (filesystem, git, GitHub)
- Modular LLM connectors
- Async scanning for performance
- Fine-grained file selection with patterns
- Diff parsing for precise code review

---

## 🧠 Custom Prompt Rules 

You can modify the system prompt used by creating a file named `saist.rules` in your working directory.

This file supports the following YAML keys:

PROMPT_OVERRIDE - Fully replaces the system prompt 
PROMPT_PRE - Adds text before the existing prompt 
PROMPT_POST - Adds text after the existing prompt 

If multiple keys are defined, `PRE` and `POST` will wrap around the override text.

---

### 📝 `saist.rules.example`

```yaml
# Example prompt modification

# Use this to completely override the system prompt:
PROMPT_OVERRIDE: "Identify any potential vulnerabilites in the following code. Focus on input validation"

# Use these to prepend or append context to the prompt
PROMPT_PRE: "You are reviewing critical code. Please be strict.\n\n"
PROMPT_POST: "\n\nPlease provide practical advice."

---

## 🛣️ Roadmap

- Ability to influence the prompts
- Create a Github action
- Add additional LLM support
- Add additional SCM sources
- SaaS platform version (maybe 👀)

---

## 🤝 Contributing

Pull requests are welcome!  

---

## ⭐ Final Note

If you like it — **star it** ⭐, **use it**, and **share feedback**!  
AI-assisted code scanning just got a lot more magical. 🪄

