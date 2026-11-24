# Moonwalking Local Assistant

The local assistant uses the Ollama model installed on this computer for routine,
high-volume development work without consuming hosted Codex or Claude credits.

## Good uses

- Ask grounded questions about selected project files.
- Review the current tracked Git diff before requesting a hosted-model review.
- Triage backend, frontend, or test logs.
- Summarize a long implementation file before working on it.

Use Codex or Claude for complex architecture, security-sensitive changes, broad
multi-file edits, and final verification. The local 9B model should not be trusted
to navigate or modify the full repository autonomously.

## Commands

For the simplest workflow, double-click `Moonwalking Local AI.cmd` in the project
folder. It opens the local browser interface with three workspaces:

- Project Chat for grounded questions with optional project files.
- Change Review for inspecting the current tracked Git diff.
- Log Triage for pasted errors, test failures, and runtime logs.

The interface runs only on `127.0.0.1:8765`. Closing the browser tab does not send
conversation content anywhere.

Run these from the repository root in PowerShell:

```powershell
python scripts/local_ai.py ask "Which files own the active dashboard?"
```

Include specific files when the question needs more evidence:

```powershell
python scripts/local_ai.py ask "Explain how alerts are deduplicated" `
  --file backend/alerts_engine.py `
  --file docs/alerts_engine_spec.md
```

Review current tracked changes:

```powershell
python scripts/local_ai.py review
```

Triage a saved log:

```powershell
python scripts/local_ai.py triage backend.local.stdout
```

Paste or pipe log text through standard input:

```powershell
Get-Content .runtime/backend.log -Tail 300 | python scripts/local_ai.py triage -
```

## Grounding and safety

- The helper calls only the local Ollama API at `127.0.0.1:11434`.
- The default model is `qwen3.5:9b`.
- Project sources are inserted directly into the prompt so the model does not need
  to discover files with agent tools.
- Files outside the repository and common credential or secret files are rejected.
- Large sources are truncated to keep the request within a practical local context.
- Generated answers remain suggestions and must still be verified before code changes.
- The browser server accepts requests only through `localhost` or `127.0.0.1`.

Optional environment variables:

- `MOONWALKING_LOCAL_MODEL`: change the Ollama model name.
- `MOONWALKING_OLLAMA_URL`: change the local Ollama chat endpoint.
