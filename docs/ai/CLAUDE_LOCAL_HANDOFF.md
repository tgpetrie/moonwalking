# Claude local workspace

On Tom's Windows PC, open this folder in Claude:

`C:\Users\tgpet\Projects\Moonwalking-Claude`

It is a separate worktree of the independent local repository at
`C:\Users\tgpet\Projects\Moonwalking`, with branch `claude/local-review`.
Both working files and the common Git directory are outside OneDrive.
Select this folder explicitly in Claude's workspace/folder picker; an existing
Claude conversation may still be attached to the old OneDrive folder.

## Current work

- The scorecard and sell-side branches are combined in `codex/integrate-production`.
- Integration checkpoint `51c35fb1` contains both features and the corrected P2.6
  Portfolio Risk Board backlog entry. The storage handoff is committed afterward.
- The combined code passed 482 frontend tests, 546 backend tests (65 skipped),
  the frontend build, guardrails, and production connectivity checks.
- P2.6 is specified but not built at this checkpoint. Check the current main
  local worktree's branch and status before assuming implementation ownership.
- The user is holding this work locally before push or deployment. Do not push,
  deploy, or change production as part of opening or reviewing this workspace.
- The old `finish_claude_codex_merge.py --apply` procedure is not part of this
  handoff. Its earlier dry-run/app-closure prerequisites have not been satisfied.

## Resume safely

Read `AGENTS.md`, `CLAUDE.md`, `docs/ai/AI_INDEX.md`, the top of `HANDOFF.md`, and
`MW_BACKLOG.md`. Check remote, branch, status, worktrees, and the Git common
directory. Work only in this Claude worktree; review and merge commits to
coordinate with Codex instead of editing Codex's active files.

This transfers code and Git history only. Secrets, runtime databases, and local
dependencies have not been copied from OneDrive. Do not scan the old checkout
or copy its environments to make startup work. Install dependencies locally;
coordinate a separate, deliberate migration if existing application data is needed.
