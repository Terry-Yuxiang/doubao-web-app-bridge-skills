#!/usr/bin/env python3
"""
Doubao conversation store — DOM-based implementation.

Extracts the conversation directly from the rendered Doubao page DOM using
Chrome DevTools Protocol (CDP).

Doubao DOM structure (verified):
  User messages:     [data-testid="send_message"]
  Assistant messages: [data-testid="receive_message"]
  Text content:      [data-testid="message_text_content"] or [data-testid="message_content"]
  Conversation URL:  https://www.doubao.com/chat/{numericId}

Each saved record contains:
  turn        — 1-indexed round number (user+assistant = 1 turn)
  role        — "user" | "assistant"
  text        — prose text visible in the message
  artifacts   — list of {title, artifact_type, lang, code} for fenced code blocks
  timestamp   — ISO-8601 UTC
  source      — "dom"
"""

import argparse
import asyncio
import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import websockets

ROOT = Path(__file__).resolve().parents[1]


def _resolve_conv_dir() -> Path:
    import os
    env = os.environ.get('DOUBAO_BRIDGE_CONV_DIR')
    if env:
        return Path(env).expanduser()
    config_path = ROOT / 'config.json'
    if not config_path.exists():
        config_path = ROOT / 'config.example.json'
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding='utf-8'))
            custom = cfg.get('doubaoBridge', {}).get('conversationsDir')
            if custom:
                return Path(custom).expanduser()
        except Exception:
            pass
    return Path.home() / '.ai-bridge' / 'doubao-bridge' / 'conversations'


CONV_DIR = _resolve_conv_dir()
CONV_DIR.mkdir(parents=True, exist_ok=True)


def conv_subdir(stem: str) -> Path:
    d = CONV_DIR / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_conversation(query: str):
    q = query.strip()
    tokens = [t.lower() for t in re.split(r'[^a-zA-Z0-9]+', q) if t]
    raw_tokens = re.split(r'[^a-zA-Z0-9]+', q)
    caps_tokens = [t.lower() for t in raw_tokens if t.isupper() and 2 <= len(t) <= 6]

    results = []
    for d in sorted(CONV_DIR.iterdir()):
        meta_file = d / 'meta.json'
        if not d.is_dir() or not meta_file.exists():
            continue
        try:
            m = json.loads(meta_file.read_text(encoding='utf-8'))
        except Exception:
            continue

        chat_id = m.get('chatId', '')
        title = m.get('title', '').strip()
        tags = ' '.join(m.get('tags', []))
        corpus = (d.name + ' ' + title + ' ' + tags).lower()
        corpus_words = re.findall(r'[a-zA-Z0-9]+', corpus)
        title_words = re.findall(r'[a-zA-Z\u4e00-\u9fff]+', title + ' ' + tags)
        title_initials = [w[0].lower() for w in title_words if w and w[0].isascii()]

        if q.lower() in chat_id:
            score = 100
        else:
            score = 0
            score += sum(1 for t in tokens if t in corpus)
            score += sum(1 for t in tokens
                         if any(w.startswith(t) for w in corpus_words) and t not in corpus)
            for ct in caps_tokens:
                n = len(ct)
                matched_consec = any(
                    title_initials[i:i+n] == list(ct)
                    for i in range(max(0, len(title_initials) - n + 1))
                )
                if matched_consec:
                    score += 3
                    continue
                idx = 0
                for ch in ct:
                    while idx < len(title_initials) and title_initials[idx] != ch:
                        idx += 1
                    if idx < len(title_initials):
                        idx += 1
                    else:
                        break
                else:
                    score += 2

        if score > 0:
            results.append({
                'chatId': chat_id,
                'title': title,
                'dir': str(d),
                'savedAt': m.get('savedAt', ''),
                'totalTurns': m.get('totalTurns', 0),
                'score': score,
            })

    results.sort(key=lambda x: (-x['score'], x['savedAt']))
    return results


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str) -> str:
    # Handle Chinese titles: transliterate to pinyin-safe slug
    text = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', text.strip().lower()).strip('-')
    # Strip non-ASCII for filesystem safety
    text = re.sub(r'[^\x00-\x7F]+', '', text).strip('-')
    return text[:80] or 'doubao-chat'


def get_doubao_page():
    with urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=5) as r:
        pages = json.loads(r.read().decode())
    doubao_pages = [
        p for p in pages
        if p.get('type') == 'page' and 'doubao.com' in p.get('url', '')
    ]
    if not doubao_pages:
        raise SystemExit('Doubao page not found on CDP port 9222')
    return doubao_pages[-1]


async def cdp_eval(ws_url, expression, await_promise=False):
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        await ws.send(json.dumps({
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {'expression': expression, 'returnByValue': True, 'awaitPromise': await_promise}
        }))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get('id') == 1:
                return msg.get('result', {}).get('result', {}).get('value')


# ---------------------------------------------------------------------------
# DOM extraction
# ---------------------------------------------------------------------------

JS_EXTRACT_DOM = r'''
(() => {
  // Doubao renders user messages in [data-testid="send_message"]
  // and assistant messages in [data-testid="receive_message"]
  // Text content lives in [data-testid="message_text_content"] or [data-testid="message_content"]

  const allSend = Array.from(document.querySelectorAll('[data-testid="send_message"]'));
  const allRecv = Array.from(document.querySelectorAll('[data-testid="receive_message"]'));

  const combined = [
    ...allSend.map(el => ({el, role: 'user'})),
    ...allRecv.map(el => ({el, role: 'assistant'})),
  ];
  combined.sort((a, b) =>
    (a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1
  );

  const messages = combined.map(({el, role}, idx) => {
    const textEl = el.querySelector('[data-testid="message_text_content"]')
      || el.querySelector('[data-testid="message_content"]')
      || el;
    const text = (textEl.innerText || '').trim();

    const codeBlocks = Array.from(el.querySelectorAll('pre code')).map(c => ({
      lang: (c.className.match(/language-(\S+)/) || [])[1] || 'text',
      code: (c.innerText || '').trim(),
    })).filter(cb => cb.code);

    return {role, text, codeBlocks, domIndex: idx};
  }).filter(m => m.text || m.codeBlocks.length > 0);

  return JSON.stringify({source: 'dom', messages});
})()
'''

JS_PAGE_META = r'''
(() => {
  const url = location.href;
  // Doubao conversation URLs: https://www.doubao.com/chat/{numericId}
  const chatId = (url.match(/\/chat\/(\d+)/i) || [])[1] || 'unknown';
  // Title from sidebar active item or page title
  const titleEl = document.querySelector('[data-testid="chat_list_item_title"]');
  const title = (titleEl ? titleEl.innerText : document.title).trim()
    .replace(/\s*[-|]\s*豆包.*$/i, '').trim() || '豆包对话';
  return JSON.stringify({title, url, chatId});
})()
'''


# ---------------------------------------------------------------------------
# DOM message parsing
# ---------------------------------------------------------------------------

def assign_turns_from_dom(dom_data: dict) -> list:
    messages = dom_data.get('messages', [])
    records = []
    turn = 0

    for msg in messages:
        role = msg.get('role', '')
        if role not in ('user', 'assistant'):
            continue
        if role == 'user':
            turn += 1

        text = (msg.get('text') or '').strip()
        code_blocks = msg.get('codeBlocks') or []

        artifacts = []
        for j, cb in enumerate(code_blocks):
            code = (cb.get('code') or '').strip()
            lang = cb.get('lang') or 'text'
            if code:
                artifacts.append({
                    'title': f'code-block-{j+1}',
                    'artifact_type': 'code',
                    'lang': lang,
                    'code': code,
                })

        if not text and not artifacts:
            continue

        record = {
            'turn': turn,
            'role': role,
            'text': text,
            'timestamp': now_iso(),
            'source': 'dom',
        }
        if artifacts:
            record['artifacts'] = artifacts
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_existing_ids(path: Path):
    seen = set()
    if not path.exists():
        return seen
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            obj = json.loads(line)
            if 'turn' in obj and 'role' in obj:
                seen.add((obj['turn'], obj['role']))
        except Exception:
            continue
    return seen


def append_jsonl(path: Path, rows):
    with path.open('a', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def export_to_md(jsonl_path: Path, meta_path: Path) -> Path:
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    records = [json.loads(l) for l in jsonl_path.read_text(encoding='utf-8').splitlines() if l.strip()]

    lines = []
    title = meta.get('title', '').strip()
    lines.append(f'# {title}')
    lines.append('')
    lines.append('| Field | Value |')
    lines.append('|---|---|')
    lines.append(f'| Chat ID | `{meta.get("chatId","")}` |')
    lines.append(f'| URL | {meta.get("url","")} |')
    lines.append(f'| Project | {meta.get("project","")} |')
    lines.append(f'| Turns | {meta.get("totalTurns","")} |')
    lines.append(f'| Saved | {meta.get("savedAt","")} |')
    lines.append('')

    turns: dict = defaultdict(dict)
    for rec in records:
        turns[rec.get('turn', 0)][rec.get('role', 'unknown')] = rec

    for turn_num in sorted(turns.keys()):
        lines.append('---')
        lines.append(f'# Round {turn_num}')
        lines.append('')
        for role_key, heading in [('user', 'User'), ('assistant', 'Assistant')]:
            rec = turns[turn_num].get(role_key)
            if not rec:
                continue
            lines.append(f'## {heading}')
            lines.append('')
            text = rec.get('text', '').strip()
            if text:
                lines.append(text)
                lines.append('')
            for a in rec.get('artifacts', []):
                lines.append(f'### Artifact: {a["title"]}')
                lines.append('')
                lines.append(f'```{a.get("lang","text")}')
                lines.append(a.get('code', '').strip())
                lines.append('```')
                lines.append('')

    md_path = jsonl_path.with_suffix('.md')
    md_path.write_text('\n'.join(lines), encoding='utf-8')
    return md_path


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def cmd_find(query: str):
    print(json.dumps(find_conversation(query), ensure_ascii=False, indent=2))


def cmd_list():
    rows = []
    for d in sorted(CONV_DIR.iterdir()):
        meta_file = d / 'meta.json'
        if not d.is_dir() or not meta_file.exists():
            continue
        try:
            m = json.loads(meta_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        rows.append({
            'chatId': m.get('chatId', ''),
            'title': m.get('title', '').strip(),
            'tags': m.get('tags', []),
            'dir': str(d),
            'savedAt': m.get('savedAt', '')[:10],
            'totalTurns': m.get('totalTurns', 0),
        })
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def cmd_tag(chat_id_prefix: str, tags: list):
    results = find_conversation(chat_id_prefix)
    if not results:
        raise SystemExit(f'No conversation found matching: {chat_id_prefix}')
    target = results[0]
    meta_path = Path(target['dir']) / 'meta.json'
    m = json.loads(meta_path.read_text(encoding='utf-8'))
    existing = set(m.get('tags', []))
    existing.update(tags)
    m['tags'] = sorted(existing)
    meta_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'chatId': m['chatId'], 'tags': m['tags']}, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    ap = argparse.ArgumentParser(description='Persist current Doubao chat to JSONL + metadata (DOM-based)')
    ap.add_argument('--project', default='general')
    ap.add_argument('--export-md', action='store_true')
    ap.add_argument('--find', metavar='QUERY')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--tag', nargs='+', metavar='TAG')
    args = ap.parse_args()

    if args.find:
        cmd_find(args.find)
        return
    if args.list:
        cmd_list()
        return
    if args.tag:
        if len(args.tag) < 2:
            ap.error('--tag requires a chatId prefix followed by at least one tag')
        cmd_tag(args.tag[0], args.tag[1:])
        return

    page = get_doubao_page()
    ws_url = page['webSocketDebuggerUrl']

    meta_raw = await cdp_eval(ws_url, JS_PAGE_META)
    if not meta_raw:
        raise SystemExit('Could not read page meta')
    meta_info = json.loads(meta_raw)
    title = meta_info.get('title', '豆包对话')
    url = meta_info.get('url', '')
    chat_id = meta_info.get('chatId', 'unknown')

    dom_raw = await cdp_eval(ws_url, JS_EXTRACT_DOM)
    if not dom_raw:
        raise SystemExit('DOM extraction returned no data')
    dom_data = json.loads(dom_raw)
    if 'error' in dom_data:
        raise SystemExit(f"DOM extraction error: {dom_data['error']}")

    records = assign_turns_from_dom(dom_data)
    if not records:
        raise SystemExit('No messages found in DOM — is a Doubao conversation open?')

    slug = slugify(title.strip())
    stem = f"{slug}--{chat_id}" if slug else f"doubao-chat--{chat_id}"
    conv_dir = conv_subdir(stem)
    meta_path = conv_dir / 'meta.json'
    jsonl_path = conv_dir / 'conversation.jsonl'

    meta_path.write_text(json.dumps({
        'chatId': chat_id,
        'title': title,
        'url': url,
        'project': args.project,
        'savedAt': now_iso(),
        'source': 'dom',
        'totalTurns': max((r['turn'] for r in records), default=0),
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    seen = load_existing_ids(jsonl_path)
    new_rows = [r for r in records if (r['turn'], r['role']) not in seen]
    append_jsonl(jsonl_path, new_rows)

    result = {
        'ok': True,
        'dir': str(conv_dir),
        'meta': str(meta_path),
        'jsonl': str(jsonl_path),
        'totalMessages': len(records),
        'newMessagesWritten': len(new_rows),
    }
    if args.export_md:
        md_path = export_to_md(jsonl_path, meta_path)
        result['md'] = str(md_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
