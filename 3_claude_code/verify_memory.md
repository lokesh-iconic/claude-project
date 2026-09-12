# Memory Verification Guide

How to confirm which Claude Code configuration files are actually loaded
in a session, and resolve any mismatches from what you expected.

## Step 1: Check Loaded Memory Files with `/memory`

In an interactive Claude Code session, type:

```
/memory
```

This shows:
- **CLAUDE.md locations** — user-level (`~/.claude/CLAUDE.md`) and project-level (`./CLAUDE.md`)
- **CLAUDE.local.md** — personal per-project notes
- **Auto memory** — toggle and browse Claude's auto-saved notes
- Select any file to open and edit it

### What to look for

You should see entries for:
- `CLAUDE.md` (project root) ← our main project instructions
- `1_agents_and_workflows/CLAUDE.md` ← loads on demand when reading files in that directory
- Auto memory directory (if enabled)

## Step 2: Verify Context with `/context`

Type:

```
/context
```

This shows a **colored grid** of what's consuming the context window, including:
- **Memory files** — which CLAUDE.md files are loaded
- **Conversation history** — how much space it takes
- **Tool outputs** — recent file reads, command outputs

### Confirming the hierarchy

1. At session start, only the **root CLAUDE.md** loads automatically
2. Ask Claude to read a file in `1_agents_and_workflows/`:
   ```
   Read 1_agents_and_workflows/shared.py
   ```
3. Run `/context` again — you should now see **both** CLAUDE.md files loaded

This confirms the hierarchy: root applies everywhere, directory-level loads
on demand when Claude accesses files in that subdirectory.

## Step 3: Check Settings with `/status`

Type:

```
/status
```

Look at the **Setting sources** line. You should see:
- `Project settings` — from `.claude/settings.json`
- `Project local settings` — from `.claude/settings.local.json` (if it has content)

This confirms your settings files are being read.

## Step 4: Verify Custom Commands

Type `/` and start typing `summarize`. You should see:

```
/project:summarize-changes
```

in the autocomplete list. This confirms the custom command in
`.claude/commands/summarize-changes.md` was discovered.

## Troubleshooting Mismatches

### CLAUDE.md not loading

1. Check the file exists at the expected path (root or subdirectory)
2. Make sure you're running Claude Code from the project root
3. Subdirectory CLAUDE.md files load **on demand**, not at startup — read a
   file in that directory first

### Settings not applying

1. Run `/status` and check `Setting sources`
2. Verify the JSON is valid — no trailing commas or comments
3. Remember: managed settings override everything; project overrides user

### Custom command missing

1. Check the file is at `.claude/commands/<name>.md`
2. The command name comes from the filename (without `.md`)
3. Project commands appear as `/project:<name>` in the picker

### Auto memory issues

1. Run `/memory` and check the auto memory toggle
2. Browse `~/.claude/projects/<project>/memory/` for saved memories
3. The first 200 lines of `MEMORY.md` load per session
