Handle the following Doubao bridge subcommand from $ARGUMENTS.

Read the project root at the working directory. The venv is at `.venv/` — activate it before running any script: `. .venv/bin/activate`.

---

## Subcommands

### `start`
Enable routing mode for this session.
1. Read `state.json`, set `routingMode` to `true`, write it back.
2. Reply: "**Routing mode ON** — all subsequent messages will be forwarded to the Doubao web app."

### `end`
Disable routing mode.
1. Read `state.json`, set `routingMode` to `false` and `activeConversation` to `null`, write it back.
2. Reply: "**Routing mode OFF** — messages will be answered locally."

### `+<message>` (args starts with `+`)
Route this single message through the Doubao web bridge.
1. Extract the message: everything after the leading `+` (trim whitespace).
2. Check `state.json` for `activeConversation`. If set, navigate first:
   ```
   python scripts/doubao_web_probe.py navigate --chat-id <activeConversation>
   sleep 4
   ```
3. Send the message:
   ```
   python scripts/doubao_web_probe.py ask --question "<message>"
   ```
4. Wait for the response (poll `read` every 10s until tail stops changing, max 60s).
5. Save:
   ```
   python scripts/doubao_conversation_store.py --export-md
   ```
6. Show the assistant's response to the user.

### `conversation list`
List all saved conversations.
1. Run:
   ```
   python scripts/doubao_conversation_store.py --list
   ```
2. Display as a table:
   ```
   #  | Title                  | Chat ID           | Turns | Saved
   ---|------------------------|-------------------|-------|-------
   1  | 大语言模型解释          | 38418062256168706 | 3     | 2026-03-22
   ```
3. Note which conversation is currently active (from `state.json`).

### `conversation <name> +<message>`
Navigate to a named conversation and send a message.
Parse args: everything before ` +` is the name/query; everything after ` +` is the message.

1. Run:
   ```
   python scripts/doubao_conversation_store.py --find "<name>"
   ```
   Take the first result (highest score).

   - If **non-empty**: use the top result.
   - If **empty**: fall back to `--list` + semantic reasoning.
   - If top two have equal score: ask the user to clarify.

2. Navigate (with 4s wait for page to load):
   ```
   python scripts/doubao_web_probe.py navigate --chat-id <chatId>
   sleep 4
   python scripts/doubao_web_probe.py probe   # verify title matches
   ```
3. Update `state.json`: set `activeConversation` to the matched `chatId`.
4. Send the message:
   ```
   python scripts/doubao_web_probe.py ask --question "<message>"
   ```
5. Wait for response (poll `read` every 10s, max 60s).
6. Save:
   ```
   python scripts/doubao_conversation_store.py --export-md
   ```
7. Show the response and confirm: "Active conversation set to: **<title>**".

---

### Tagging a conversation

```
python scripts/doubao_conversation_store.py --tag <chatId-prefix> <tag1> [tag2 ...]
```

---

## Routing mode behaviour

When `state.json` has `routingMode: true`, treat every subsequent user message as a `+<message>` bridge call. Persists until `/doubao end` is called.

Check `state.json` at the start of each response when this skill is active.
