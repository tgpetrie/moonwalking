#!/usr/bin/env bash
# GitHub Copilot CLI helpers for zsh
# Drop this snippet into your ~/.zshrc or source it from there.

if command -v gh >/dev/null 2>&1; then
  # Try sourcing official alias locations installed by `gh copilot alias --install`
  if [[ -f "${HOME}/.config/gh/copilot-aliases.sh" ]]; then
    source "${HOME}/.config/gh/copilot-aliases.sh"
  elif [[ -f "${HOME}/.gh-copilot/aliases.sh" ]]; then
    source "${HOME}/.gh-copilot/aliases.sh"
  fi

  # Lightweight fallbacks calling gh directly
  copilot_explain() { gh copilot explain -- "$*"; }
  copilot_suggest() { gh copilot suggest -- "$*"; }
  copilot_review()  { gh copilot review -- "$*"; }

  alias gex='copilot_explain'
  alias gcop='copilot_suggest'
  alias grev='copilot_review'

  gcm() {
    # Suggest a short conventional commit message for staged changes
    gh copilot suggest "Write a short conventional commit message for the staged changes (type: feat/fix/docs/chore):" -- "$@"
  }
fi

# End copilot zsh snippet
#!/usr/bin/env bash
# GitHub Copilot CLI helpers (ready-to-paste into ~/.zshrc)
# Requires 'gh' + 'gh copilot' extension installed.
if command -v gh >/dev/null 2>&1; then
  # Try to source the official alias file (installed by `gh copilot alias --install`).
  if [[ -f "${HOME}/.config/gh/copilot-aliases.sh" ]]; then
    source "${HOME}/.config/gh/copilot-aliases.sh"
  elif [[ -f "${HOME}/.gh-copilot/aliases.sh" ]]; then
    source "${HOME}/.gh-copilot/aliases.sh"
  fi

  # Fallback helpers if official aliases aren't present
  copilot_explain() { gh copilot explain -- "$*"; }
  copilot_suggest() { gh copilot suggest -- "$*"; }
  copilot_review()  { gh copilot review -- "$*"; }

  alias gex='copilot_explain'
  alias gcop='copilot_suggest'
  alias grev='copilot_review'

  gcm() {
    gh copilot suggest "Write a short conventional commit message for the staged changes (type: feat/fix/docs/chore):" -- "$@"
  }
fi

echo "# Add the contents of this file into your ~/.zshrc or source it from there to enable Copilot CLI helpers"
