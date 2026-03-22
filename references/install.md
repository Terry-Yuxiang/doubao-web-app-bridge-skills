# Installation

## Required local environment

- macOS
- Google Chrome
- Python 3
- Chrome DevTools Protocol access on port `9222`

## Python dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```

Current required packages:
- `websockets`

## Runtime expectation

This skill operates via the **Doubao web bridge via doubao.com**:
- Uses browser automation and CDP
- Requires a Chrome instance running with `--remote-debugging-port=9222`
- Requires being logged in to doubao.com in that browser

## Starting the automation browser

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/doubao-cdp-profile
```

Then open `https://www.doubao.com/chat/` and log in before running any scripts.

## Important: login required for navigate

Doubao allows chatting without login, but navigating back to a saved conversation URL requires an active login session. Always log in before running the full workflow.

## Verification steps

### 1. Probe — confirm the bridge sees the Doubao page

```bash
. .venv/bin/activate
python scripts/doubao_web_probe.py probe
```

Expected: JSON with `"url"` containing `doubao.com` and `"inputs"` showing `chat_input_input` textarea.

### 2. Ask and read back (Round 1)

```bash
python scripts/doubao_web_probe.py ask --question "Round 1: 用一句话解释什么是大语言模型"
sleep 8
python scripts/doubao_web_probe.py read
```

Expected: `sampleTail` contains Doubao's reply. URL changes to `https://www.doubao.com/chat/{numericId}`.

### 3. Save Round 1

```bash
python scripts/doubao_conversation_store.py --export-md --project bridge-testing
```

Expected:
```json
{
  "ok": true,
  "dir": "/Users/<you>/.ai-bridge/doubao-bridge/conversations/<slug>--<chatId>",
  "totalMessages": 2,
  "newMessagesWritten": 2,
  "md": "...conversation.md"
}
```

### 4. Send Round 2 and save incrementally

```bash
python scripts/doubao_web_probe.py ask --question "Round 2: 大语言模型和传统搜索引擎的核心区别是什么？"
sleep 8
python scripts/doubao_conversation_store.py --export-md --project bridge-testing
```

Expected: `totalMessages: 4`, `newMessagesWritten: 2`.

### 5. Navigate to the saved conversation and continue (Round 3)

```bash
# Get chatId from meta
cat ~/.ai-bridge/doubao-bridge/conversations/<slug>--<chatId>/meta.json

# Navigate (wait 4s for page to load before asking)
python scripts/doubao_web_probe.py navigate --chat-id <chatId>
sleep 4
python scripts/doubao_web_probe.py probe   # verify URL matches

python scripts/doubao_web_probe.py ask --question "Round 3: 举一个大语言模型在实际工作中帮助提效的具体例子"
sleep 10
python scripts/doubao_conversation_store.py --export-md --project bridge-testing
```

Expected: `totalMessages: 6`, `newMessagesWritten: 2`.

### 6. Verify Markdown structure

```bash
cat ~/.ai-bridge/doubao-bridge/conversations/<slug>--<chatId>/conversation.md | head -40
```

Expected:
```
# <title>
| Field | Value |
...
---
# Round 1
## User
...
## Assistant
...
```

Only claim the bridge is working if each step above produces the expected output.
