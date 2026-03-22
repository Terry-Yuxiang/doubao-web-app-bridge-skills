# Bridge Patterns

General patterns for using the Doubao web bridge effectively.

## Context packet structure

```
OS: macOS (Darwin)
Repo: /path/to/repo
Framework: Next.js 14 / Node 20
Goal: <what you're trying to accomplish>
Command: <exact command being run>
Error:
<exact error output, trimmed to the relevant part>
Constraints: production env, no destructive changes
```

## Forwarding prompts

### Diagnosis mode
```
[Context packet above]

Task: Diagnose this error. Identify the root cause and the most likely fix.
Do not write code yet — just explain what is wrong and why.
```

### Patch-plan mode
```
[Context packet above]

Task: Write the minimal patch to fix this. Show only changed lines with file paths.
```

### Review mode
```
[Context packet above]

Planned fix:
<your proposed change>

Task: Review this fix. Is it correct? Will it break anything else?
```

### Compare-options mode
```
[Context packet above]

Task: Compare these approaches:
1. <option A>
2. <option B>

Evaluate trade-offs: correctness, performance, maintainability, risk.
Recommend one and explain why.
```

## Polling for response completion

```bash
python scripts/doubao_web_probe.py ask --question "..."
sleep 8
python scripts/doubao_web_probe.py read   # tail1
sleep 8
python scripts/doubao_web_probe.py read   # tail2 — if same as tail1, done
```

Max polling: 60s for most tasks, 120s for long code generation.

## After navigate, always wait

```bash
python scripts/doubao_web_probe.py navigate --chat-id <chatId>
sleep 4   # Doubao needs time to fully render the conversation
python scripts/doubao_web_probe.py probe  # verify before asking
```

## Saving after each round

```bash
python scripts/doubao_conversation_store.py --export-md
```

Re-running is safe — only new turns are appended.

## Tagging for retrieval

```bash
python scripts/doubao_conversation_store.py --tag <chatId-prefix> <tag1> [tag2 ...]
```

## When NOT to use the bridge

- For questions answerable in under 30 seconds locally
- When the user explicitly wants a local answer
- When the browser is not running or not logged in to doubao.com
