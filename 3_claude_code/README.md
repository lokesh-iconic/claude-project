# Claude Code — Deliberate Repository Configuration

Configure Claude Code deliberately across a real repository: correct CLAUDE.md hierarchy, custom commands, settings, headless mode, and memory verification.

## Problem Statement

Rather than using Claude Code casually, operate it deliberately: configure the CLAUDE.md hierarchy correctly across user, project, and directory scope, create custom slash commands, run headless tasks, and verify what configuration files are actually loaded.

## Project Structure

```
3_claude_code/
├── README.md                               ← You are here
├── validate_setup.py                       ← Run this to validate the configuration
├── CLAUDE.md                               ← Project-level CLAUDE.md
├── sample_subfolder/
│   └── CLAUDE.md                           ← Directory-level CLAUDE.md (different conventions)
├── .claude/
│   ├── settings.json                       ← Shared project settings
│   ├── settings.local.json                 ← Personal local settings (gitignored)
│   └── commands/
│       └── summarize-changes.md            ← Custom slash command
├── scripts/
│   ├── headless_summary.py                 ← Headless mode (-p) demo (Python)
│   └── headless_summary.ps1                ← Headless mode (-p) demo (PowerShell)
└── verify_memory.md                        ← Memory verification guide
```

## Quick Start

```bash
# From the claude_project root directory:

# 1. Install dependencies
uv sync

# 2. Validate the entire setup (checks all config files, settings, commands)
uv run python .\3_claude_code\validate_setup.py

# 3. Validate and also test headless mode with a live Claude Code call
uv run python .\3_claude_code\validate_setup.py --headless
```

## Setup (Activating the Configuration)

To actually use these config files with Claude Code, copy them to the repo root:

```bash
copy 3_claude_code\CLAUDE.md .\CLAUDE.md
xcopy 3_claude_code\.claude .\.claude /E /I
copy 3_claude_code\sample_subfolder\CLAUDE.md 1_agents_and_workflows\CLAUDE.md
```

Then verify in an interactive session:
```bash
claude
# Type:  /memory
# Type:  /context
```

## What Was Built

### 1. Repository Initialization & Settings (`settings.json`)

**File**: [`.claude/settings.json`](.claude/settings.json)

Shared project settings committed to version control so teammates inherit them:

```json
{
  "permissions": {
    "allow": ["Bash(uv sync)", "Bash(uv run *)", "Bash(pytest *)", "Bash(git log *)"],
    "deny": ["Read(./.env)", "Read(./.env.*)"]
  }
}
```

**File**: [`.claude/settings.local.json`](.claude/settings.local.json)

Personal local settings (gitignored) — for per-developer sandbox URLs, testing overrides, etc.

### 2. CLAUDE.md Hierarchy (Project + Directory)

Two CLAUDE.md files demonstrate the scoping hierarchy:

| Scope | File | Purpose |
|-------|------|---------|
| **Project** | [`CLAUDE.md`](CLAUDE.md) | Build commands, coding standards, project architecture — applies to every session |
| **Directory** | [`sample_subfolder/CLAUDE.md`](sample_subfolder/CLAUDE.md) | Agent-specific conventions for hooks, subagents, naming — applies only when Claude reads files in that subdirectory |

**How the hierarchy works**:
- At session start, only the **project-level** CLAUDE.md loads
- When Claude reads a file inside a subdirectory, that directory's CLAUDE.md also loads
- Both apply simultaneously — directory rules supplement, never override, project rules
- Run `/context` to see which files are loaded at any point

### 3. Custom Slash Command

**File**: [`.claude/commands/summarize-changes.md`](.claude/commands/summarize-changes.md)

A reusable command accessible as `/project:summarize-changes` that replaces manually running `git log` and interpreting diffs. It:

1. Runs `git log --oneline -20` to get recent commits
2. Runs `git diff --stat HEAD~5` for changed files
3. Summarizes each change
4. Produces a structured report (activity, files, decisions, open items)

### 4. Headless Mode (`-p`)

Two scripts that run Claude Code non-interactively, capturing output as you would inside a CI/CD pipeline:

| Script | Language | Usage |
|--------|----------|-------|
| [`scripts/headless_summary.py`](scripts/headless_summary.py) | Python | `uv run python .\3_claude_code\scripts\headless_summary.py` |
| [`scripts/headless_summary.ps1`](scripts/headless_summary.ps1) | PowerShell | `.\3_claude_code\scripts\headless_summary.ps1` |

Both scripts:
- Run `claude -p "..."` as a subprocess
- Capture structured output (text and JSON formats)
- Save results to `scripts/output/`
- Print a summary to the console

**Direct headless usage**:
```bash
# Text output
claude -p "List all Python files in this project"

# JSON output
claude -p "What is the project name?" --output-format json

# Pipe into another tool
claude -p "Summarize recent changes" | Out-File -FilePath summary.md
```

### 5. Memory Verification (`/memory`)

**File**: [`verify_memory.md`](verify_memory.md)

Step-by-step guide for confirming which configuration files are loaded:

| Command | What it shows |
|---------|--------------|
| `/memory` | Lists all CLAUDE.md and memory file locations; lets you edit them |
| `/context` | Visualizes what's in the context window, including which CLAUDE.md files loaded |
| `/status` | Shows which settings files are active (project, local, managed) |

## Architectural Decisions

### Why CLAUDE.md Instead of Just Prompts

CLAUDE.md files persist across sessions — they're read at the start of every conversation. A prompt you type is gone after `/clear`. CLAUDE.md is the difference between "Claude knows my project" and "I re-explain my project every time."

### Why a Custom Command Instead of Typing the Prompt

The `/project:summarize-changes` command encapsulates a multi-step workflow (git log → git diff → summarize → format). Typing it manually each time is:
- Error-prone (you forget a step)
- Inconsistent (different phrasing gets different results)
- Not shareable (teammates can't reuse your prompt)

The `.claude/commands/` file solves all three.

### Why Headless Mode Matters

Interactive Claude Code is for development. Headless mode (`-p`) is for automation:
- CI pipelines that generate changelogs
- Pre-commit hooks that check for issues
- Scheduled tasks that summarize daily progress
- Scripts that chain Claude output into other tools

### Settings: allow vs. deny

The `allow` list pre-approves safe, repeatable commands (`uv sync`, `pytest`, `git log`) so Claude doesn't ask permission every time. The `deny` list blocks `.env` files regardless of what Claude decides to do — a hard enforcement that prompts can't override.

## Mock vs. Live Mode

All scripts work without an API key. Claude Code uses its own authentication (configured during `claude` setup). The headless scripts capture whatever output Claude Code produces.
