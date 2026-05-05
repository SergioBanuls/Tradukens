# Tradukens

Tradukens is a local prompt translator wrapper for coding CLIs. You write a prompt in Spanish, press Enter, and Tradukens sends an English version to the selected agent.

V1 targets:

- Codex CLI
- Claude Code
- OpenCode

The runtime path is local-only after the one-time setup downloads language models.

## Install

One-command install for macOS/Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/SergioBanuls/Tradukens/main/install.sh | sh
```

Manual install:

```bash
uv tool install git+https://github.com/SergioBanuls/Tradukens.git
tradukens setup --lang es
tradukens doctor
```

From a local checkout:

```bash
uv sync
uv run tradukens setup --lang es
uv run tradukens doctor
```

## Usage

Translate text:

```bash
uv run tradukens translate "arregla este bug sin cambiar la API pública"
```

If installed globally, omit `uv run`:

```bash
tradukens translate "arregla este bug sin cambiar la API pública"
```

Measure token savings:

```bash
uv run tradukens savings "arregla este bug sin cambiar la API pública"
```

Start a wrapped Codex session:

```bash
uv run tradukens codex
```

By default this starts the official Codex TUI inside a pseudo-terminal. Codex still receives your typing while you compose, so its input box, slash commands, and multi-line editing keep their native behavior.
When a normal prompt is submitted, Tradukens intercepts Enter, clears the draft, briefly shows `Traduciendo...`, then replaces the draft with the translated prompt. Press Enter again to send it after review.
Use `Shift+Enter` for Codex's native line break before submitting the prompt.

The older non-interactive wrapper is still available:

```bash
uv run tradukens codex --mode exec
```

Start a wrapped Claude Code session:

```bash
uv run tradukens claude
```

Start a wrapped OpenCode session:

```bash
uv run tradukens opencode
```

Check the installation:

```bash
tradukens doctor
```

Inside the REPL:

- Press Enter to translate and send a prompt.
- Use `:paste` for multi-line prompts, ending with `:end`.
- Use `:quit` to exit.
- Lines beginning with `/` are passed through without translation.

## Data

Tradukens stores:

- Config in `~/.config/tradukens/config.toml`
- Models in `~/.local/share/tradukens/models`
- Text-free metrics in `~/.local/state/tradukens/metrics.jsonl`

## Distribution

Run the local release checks before tagging or publishing:

```bash
scripts/release-check.sh
```

Install from a different Git remote with:

```bash
TRADUKENS_REPO_URL=https://github.com/YOUR_USER/Tradukens.git sh install.sh
```

When the package is ready for PyPI:

```bash
uv build
uv publish
uv tool install tradukens
tradukens setup --lang es
```
