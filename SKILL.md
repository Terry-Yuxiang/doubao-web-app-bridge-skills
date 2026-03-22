---
name: doubao-web-app-bridge-skills
description: Bridge selected questions and long coding/debugging subtasks to Doubao (豆包), ByteDance's AI assistant. Use when the user wants to forward a problem to Doubao, include environment context, wait for Doubao's real response, and use that response downstream.
---

Use this skill when the user wants a **Doubao bridge**, not a purely local answer.

What this skill is for:
- forwarding selected questions to Doubao
- forwarding long coding or debugging subtasks to Doubao
- including compact but sufficient environment context
- waiting for Doubao's real answer before proceeding
- using Doubao as an external reasoning/coding assist layer

Current bridge modes:
1. **Doubao web bridge via doubao.com**
   - validated on this machine
   - uses the dedicated automation browser and Chrome CDP on port `9222`

Hard boundary:
- Never imply Doubao answered when the bridge did not actually run.
- Never present a local guess as if it came from Doubao.

Auto-bridge policy:
- Read `config.json` if present, otherwise fall back to `config.example.json`.
- Respect `doubaoBridge.autoBridgeAllowed`.
- If `autoBridgeAllowed=false`, do not auto-start Doubao without user intent.
- If `autoBridgeAllowed=true`, Doubao may be invoked automatically for long tasks.

Routing mode (session state):
- Read `state.json` at the start of each response.
- If `routingMode: true`, forward every user message to the Doubao web bridge (same as `/doubao +<message>`).
- If `activeConversation` is set, navigate to that conversation before sending.
- Routing mode is toggled via `/doubao start` and `/doubao end`.

Standard bridge workflow:
1. Decide whether the task should be forwarded to Doubao.
2. Build a compact environment context packet.
3. Send via the Doubao browser bridge.
4. Wait for Doubao's real output.
5. Use that output as guidance, patch plan, or comparison answer.
6. Tell the user when the result came from Doubao.

Important: after navigate, always wait at least 3 seconds before calling ask, to allow the page to fully render.

Multi-turn conversation save policy:
- Save after **every completed assistant turn** (not only at end of session).
- Run `scripts/doubao_conversation_store.py --export-md` after each round.
- Each conversation is stored under `~/.ai-bridge/doubao-bridge/conversations/{slug}--{chatId}/`:
  - `conversation.jsonl` — structured records, one per message
  - `meta.json` — chat ID, title, URL, total turns, saved timestamp
  - `conversation.md` — LLM-readable export (Round -> User/Assistant heading structure)
- Saving is idempotent: re-running only appends new turns.

Conversation continuation workflow:
1. Read `meta.json` to get `chatId`.
2. Navigate:
   ```
   python scripts/doubao_web_probe.py navigate --chat-id <chatId>
   sleep 4
   ```
3. Verify with `probe`.
4. Continue with `ask`.
5. Save with `doubao_conversation_store.py --export-md`.

DOM structure (verified):
- Input textarea:  `data-testid="chat_input_input"` (semi-design TEXTAREA)
- Send button:     `data-testid="chat_input_send_button"`
- User messages:   `data-testid="send_message"`
- AI messages:     `data-testid="receive_message"`
- Message text:    `data-testid="message_text_content"` or `data-testid="message_content"`
- Conversation URL: `https://www.doubao.com/chat/{numericId}`

Slash commands (`.claude/commands/`):
- `/doubao start` — enable routing mode
- `/doubao end` — disable routing mode
- `/doubao +<message>` — route a single message through the bridge
- `/doubao conversation list` — list all saved conversations
- `/doubao conversation <name> +<message>` — navigate to a named conversation and send a message

Bundled resources:
- `state.json` for current routing mode and active conversation state
- `references/install.md` for required local environment and dependency setup
- `references/bridge-patterns.md` for prompt-shaping and context-packet patterns
- `references/conversation-continuation.md` for resuming a saved conversation
- `scripts/doubao_web_probe.py` for low-level doubao.com bridge operations (probe / ask / read / navigate)
- `scripts/bridge_config.py` for config and auto-bridge policy control
- `scripts/doubao_conversation_store.py` for saving Doubao chat state into per-conversation subdirectories
