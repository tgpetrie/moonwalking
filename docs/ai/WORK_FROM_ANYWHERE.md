# Work from Anywhere

Moonwalking supports two complementary workflows.

## Work on another computer through GitHub

Use this for normal development. Each computer has its own checkout, dependencies, and Claude/Codex sessions. GitHub carries the code, project documentation, agent rules, branches, commits, and handoff state.

```powershell
gh auth login
gh repo clone tgpetrie/moonwalking Moonwalking
Set-Location Moonwalking
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-windows.ps1
```

Before leaving one computer, commit and push the active branch and update `HANDOFF.md` when the next agent needs context. On the next computer, fetch and check out that same branch. Never copy `.git`, `.claude`, `.codex`, credentials, `.env` files, virtual environments, or `node_modules` between computers.

## Control the master PC remotely

Use this when the exact desktop session, local services, or uncommitted state on the master PC is required. This PC runs Windows Home, which cannot act as a Microsoft Remote Desktop host. Configure Chrome Remote Desktop at <https://remotedesktop.google.com/access>, give this PC a recognizable name such as `Moonwalking-Master`, and protect it with a unique PIN.

Remote control does not replace Git handoffs. Commit and push completed work so another checkout can recover it if the master PC is unavailable.

## Master PC rules

- Keep the canonical checkout connected to `https://github.com/tgpetrie/moonwalking.git`.
- Push completed branches to GitHub before handing them to another computer or agent.
- Keep secrets and machine-specific state outside Git.
- Keep the PC awake and online when remote access is needed. Configure Windows power settings accordingly.
- Do not expose local development ports through router port forwarding.

## Start or resume on any computer

```powershell
git fetch --all --prune
git status --short --branch
git worktree list
git branch --all
```

Read `AGENTS.md`, `CLAUDE.md`, `docs/ai/AI_INDEX.md`, `HANDOFF.md`, and `MW_BACKLOG.md`. Then check out the named handoff branch. If work will run in parallel, create a separate branch and worktree.

