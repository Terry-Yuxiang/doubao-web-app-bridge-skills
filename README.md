# doubao-web-app-bridge-skills

A Claude Code skill that bridges the agent to the **Doubao (豆包) web app** via Chrome DevTools Protocol (CDP). Use it to forward questions or long coding/debugging tasks to Doubao, read back real responses, and persist conversations for future reference.

## What it does

- Sends messages to Doubao web app from within a Claude Code session
- Reads Doubao's responses back into the agent's context
- Saves full conversations (text + code artifacts) as JSONL + Markdown
- Navigates to previously saved conversations to continue them
- Supports routing mode: toggle all messages through the bridge with `/doubao start` / `/doubao end`

## Prerequisites

- macOS with Google Chrome
- Chrome launched with CDP on port 9222:
  ```bash
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/doubao-cdp-profile
  ```
- Logged in to doubao.com in that browser
- Python 3

## Installation

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Project layout

```
.claude/commands/
  doubao.md              <- /doubao slash command definition
references/
  install.md             <- full installation and verification steps
  bridge-patterns.md     <- context packet patterns and forwarding prompts
  conversation-continuation.md  <- how to resume a saved conversation
scripts/
  doubao_web_probe.py    <- low-level CDP bridge: probe / ask / read / navigate
  doubao_conversation_store.py  <- save current chat to conversations/
  bridge_config.py       <- read config.json / config.example.json
config.example.json      <- bridge policy (autoBridgeAllowed, defaultMode, etc.)
state.json               <- current routing mode and active conversation
SKILL.md                 <- skill definition loaded by Claude Code
```

## Slash commands

| Command | Effect |
|---|---|
| `/doubao start` | Enable routing mode — all subsequent messages forwarded to Doubao |
| `/doubao end` | Disable routing mode |
| `/doubao +<message>` | Route a single message through the bridge |
| `/doubao conversation list` | List all saved conversations |
| `/doubao conversation <name> +<message>` | Navigate to a named conversation and send a message |

`<name>` supports fuzzy matching: partial title words, abbreviations, and keywords all work.

## Key scripts

### `doubao_web_probe.py`

```bash
. .venv/bin/activate

python scripts/doubao_web_probe.py probe
python scripts/doubao_web_probe.py ask --question "Your question here"
python scripts/doubao_web_probe.py read
python scripts/doubao_web_probe.py navigate --chat-id <chatId>
python scripts/doubao_web_probe.py navigate --url https://www.doubao.com/chat/<chatId>
```

### `doubao_conversation_store.py`

Saves to `~/.ai-bridge/doubao-bridge/conversations/` (outside skills folder — survives updates):

```bash
python scripts/doubao_conversation_store.py --export-md --project my-project
python scripts/doubao_conversation_store.py --list
python scripts/doubao_conversation_store.py --find "keyword"
python scripts/doubao_conversation_store.py --tag <chatId-prefix> tag1 tag2
```

## Verification

See `references/install.md` for the full 6-step verification sequence.

Quick smoke test:
```bash
. .venv/bin/activate
python scripts/doubao_web_probe.py probe
python scripts/doubao_web_probe.py ask --question "回复：DOUBAO_BRIDGE_OK"
sleep 8
python scripts/doubao_web_probe.py read
python scripts/doubao_conversation_store.py --export-md --project bridge-testing
```

## How conversation extraction works

Uses **DOM extraction** — reads `[data-testid="send_message"]` and `[data-testid="receive_message"]` elements directly from the rendered page. No API required.

Input uses Doubao's semi-design textarea with React `__reactProps` onChange trigger (verified working).

## config.json fields

```json
{
  "doubaoBridge": {
    "enabled": true,
    "autoBridgeAllowed": false,
    "defaultMode": "diagnosis",
    "useDoubaoWeb": true,
    "requireRealResponse": true,
    "conversationsDir": "~/.ai-bridge/doubao-bridge/conversations"
  }
}
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Terry-Yuxiang/doubao-web-app-bridge-skills&type=Date)](https://star-history.com/#Terry-Yuxiang/doubao-web-app-bridge-skills&Date)

## Important constraints

- Must be logged in to doubao.com — navigate requires an active session
- Always wait 4+ seconds after navigate before calling ask
- The automation browser must be running with `--remote-debugging-port=9222`
- When acting as an AI agent: execute bash commands directly — do not invoke `/doubao` via the Skill tool
