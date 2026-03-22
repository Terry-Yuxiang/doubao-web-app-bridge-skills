#!/usr/bin/env python3
"""Low-level Doubao web bridge helper.

Works against an already logged-in doubao.com page in the dedicated
Chrome automation browser on CDP port 9222.

Commands:
- probe: inspect page state
- ask: submit a question
- read: read visible tail text from the page
- navigate: navigate to a URL or conversation
"""

import argparse
import asyncio
import json
import urllib.request
import websockets


def get_doubao_page():
    with urllib.request.urlopen('http://127.0.0.1:9222/json/list', timeout=5) as r:
        pages = json.loads(r.read().decode())
    for p in pages:
        url = p.get('url', '')
        if p.get('type') == 'page' and 'doubao.com' in url:
            return p
    raise SystemExit('Doubao page not found on CDP port 9222')


async def cdp_eval(ws_url, expression, await_promise=True):
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        await ws.send(json.dumps({
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {
                'expression': expression,
                'returnByValue': True,
                'awaitPromise': await_promise,
            }
        }))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get('id') == 1:
                return msg


def js_probe():
    return r"""
(() => {
  const inputs = Array.from(document.querySelectorAll('[data-testid="chat_input_input"], textarea[placeholder*="发消息"]')).map((el, i) => ({
    index: i,
    tag: el.tagName,
    testid: el.getAttribute('data-testid'),
    placeholder: el.getAttribute('placeholder'),
    text: (el.value || el.innerText || '').slice(0, 120),
  }));
  const buttons = Array.from(document.querySelectorAll('button, [role="button"], [data-testid]')).map((el, i) => ({
    index: i,
    tag: el.tagName,
    text: (el.innerText || '').trim().slice(0, 60),
    aria: el.getAttribute('aria-label'),
    testid: el.getAttribute('data-testid'),
    disabled: !!el.disabled,
  })).filter(x => x.text || x.aria || x.testid).slice(0, 40);
  const msgCounts = {
    send: document.querySelectorAll('[data-testid="send_message"]').length,
    receive: document.querySelectorAll('[data-testid="receive_message"]').length,
  };
  return {
    title: document.title,
    url: location.href,
    bodyTextSample: (document.body.innerText || '').slice(0, 2000),
    inputs,
    buttons,
    msgCounts,
  };
})();
"""


def js_ask(question):
    q = json.dumps(question)
    return f"""
(async () => {{
  const q = {q};

  // Dismiss any overlay
  document.dispatchEvent(new KeyboardEvent('keydown', {{key:'Escape', bubbles:true, cancelable:true}}));
  await new Promise(r => setTimeout(r, 300));

  // Find Doubao's textarea
  const ta = document.querySelector('[data-testid="chat_input_input"]')
    || document.querySelector('textarea[placeholder*="发消息"]');
  if (!ta) return {{ok: false, error: 'textarea not found'}};

  const before = document.body.innerText || '';

  // Use React __reactProps onChange to properly update state
  ta.focus();
  const propsKey = Object.keys(ta).find(k => k.startsWith('__reactProps'));
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  nativeSetter.call(ta, q);
  if (propsKey && ta[propsKey] && ta[propsKey].onChange) {{
    ta[propsKey].onChange({{ target: ta, currentTarget: ta, bubbles: true }});
  }} else {{
    ta.dispatchEvent(new InputEvent('input', {{bubbles: true, data: q, inputType: 'insertText'}}));
  }}
  await new Promise(r => setTimeout(r, 600));

  // Click send button
  const sendBtn = document.querySelector('[data-testid="chat_input_send_button"]');
  if (!sendBtn) return {{ok: false, error: 'send button not found', taValue: ta.value}};
  if (sendBtn.disabled) return {{ok: false, error: 'send button disabled', taValue: ta.value}};

  sendBtn.click();
  await new Promise(r => setTimeout(r, 1200));

  const after = document.body.innerText || '';
  return {{ok: true, bodyChanged: before !== after, hasQuestionAfter: after.includes(q)}};
}})();
"""


def js_read():
    return r"""
(() => {
  const txt = document.body.innerText || '';
  const lines = txt.split('\n').filter(Boolean);
  return {
    title: document.title,
    url: location.href,
    sampleTail: lines.slice(-120).join('\n').slice(-9000),
  };
})();
"""


def js_navigate(url):
    u = json.dumps(url)
    return f"window.location.href = {u};"


async def main():
    ap = argparse.ArgumentParser(description='Low-level Doubao web bridge helper')
    ap.add_argument('command', choices=['probe', 'ask', 'read', 'navigate'])
    ap.add_argument('--question')
    ap.add_argument('--url', help='URL to navigate to')
    ap.add_argument('--chat-id', help='Doubao conversation ID to resume')
    args = ap.parse_args()

    if args.command == 'ask' and not args.question:
        ap.error('ask command requires --question')
    if args.command == 'navigate' and not args.url and not args.chat_id:
        ap.error('navigate command requires --url or --chat-id')

    page = get_doubao_page()
    ws = page['webSocketDebuggerUrl']

    if args.command == 'navigate':
        target_url = args.url or f'https://www.doubao.com/chat/{args.chat_id}'
        expr = js_navigate(target_url)
    elif args.command == 'probe':
        expr = js_probe()
    elif args.command == 'ask':
        expr = js_ask(args.question)
    else:
        expr = js_read()

    result = await cdp_eval(ws, expr, await_promise=(args.command in ('ask',)))

    if args.command == 'navigate':
        target_url = args.url or f'https://www.doubao.com/chat/{args.chat_id}'
        err = result.get('error', {})
        val = result.get('result', {}).get('result', {}).get('value')
        if (err.get('code') == -32000 and 'navigated' in err.get('message', '').lower()) \
                or val == target_url:
            print(json.dumps({'ok': True, 'navigatedTo': target_url}, indent=2))
        else:
            print(json.dumps(val if val is not None else result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(
            result.get('result', {}).get('result', {}).get('value', result),
            ensure_ascii=False, indent=2
        ))


if __name__ == '__main__':
    asyncio.run(main())
