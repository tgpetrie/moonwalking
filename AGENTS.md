# Moonwalking Agent Workflow

These rules apply to every agent working in this repository.

## Canonical repository

- Use `C:\Users\tgpet\OneDrive\Documents\Moonwalking` as the canonical checkout.
- Do not use `DEVv\recovered\Moonwalking` for development, merging, or history repair.
- Treat committed Git history as the source of truth. Imported chat history provides context but does not override the repository state.

## Before changing files

1. Run `git fetch --all --prune`.
2. Inspect `git status --short --branch`, recent `git log`, `git worktree list`, and the current diff.
3. Read `docs/ai/AI_INDEX.md`, `HANDOFF.md`, and `MW_BACKLOG.md`.
4. Check whether another agent has active or uncommitted work that overlaps the requested files.

## Protect active work

- Do not switch branches, merge, rebase, reset, restore, clean, or discard changes until every uncommitted file has been identified and preserved.
- Do not edit another agent's active worktree.
- Use a separate named branch and worktree for parallel Claude and Codex work.
- Resolve overlapping work through commits and reviewed diffs rather than copying files between active worktrees.

## Handoff requirements

Before handing work to another agent or declaring it complete:

1. Run the relevant tests and checks.
2. Commit coherent changes with a descriptive message.
3. Push the branch unless the user explicitly requests a local-only checkpoint.
4. Report the branch, commit, checks run, and any remaining modified or untracked files.

