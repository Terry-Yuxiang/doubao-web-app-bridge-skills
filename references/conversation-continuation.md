# Conversation Continuation

## Storage layout

Default: `~/.ai-bridge/doubao-bridge/conversations/`
Override: `doubaoBridge.conversationsDir` in `config.json`, or `DOUBAO_BRIDGE_CONV_DIR` env var.

```
~/.ai-bridge/doubao-bridge/conversations/
  {slug}--{chatId}/
    meta.json            <- chatId, title, URL, project, savedAt, totalTurns, tags
    conversation.jsonl   <- one JSON record per message
    conversation.md      <- LLM-readable Markdown export
```

## When to save

After every completed assistant turn:
```bash
python scripts/doubao_conversation_store.py --export-md
```

Re-running is safe — deduplication by (turn, role).

## How to resume

```bash
# 1. Find the chatId
cat ~/.ai-bridge/doubao-bridge/conversations/<subdir>/meta.json
# or: python scripts/doubao_conversation_store.py --find "keyword"

# 2. Navigate (wait 4s — Doubao needs time to render)
python scripts/doubao_web_probe.py navigate --chat-id <chatId>
sleep 4
python scripts/doubao_web_probe.py probe   # verify URL and title

# 3. Continue
python scripts/doubao_web_probe.py ask --question "Your follow-up"
sleep 10
python scripts/doubao_conversation_store.py --export-md
```

## Conversation Markdown format

```markdown
# Conversation title
| Field | Value |
...
---
# Round 1
## User
[message]
## Assistant
[reply]
---
# Round 2
...
```

## Caution

- Must be logged in to doubao.com — navigate to specific conversations fails without login.
- Always wait at least 4 seconds after navigate before calling ask.
- Conversation URLs: `https://www.doubao.com/chat/{numericId}`.
