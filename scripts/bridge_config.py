#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config.json'
EXAMPLE = ROOT / 'config.example.json'


def load_config():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding='utf-8'))
    if EXAMPLE.exists():
        return json.loads(EXAMPLE.read_text(encoding='utf-8'))
    return {"doubaoBridge": {"enabled": True, "autoBridgeAllowed": False}}


def save_config(data):
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description='Doubao bridge config helper')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('show').set_defaults(action='show')
    x = sub.add_parser('set-auto-bridge')
    x.add_argument('value', choices=['true', 'false'])
    x.set_defaults(action='set_auto')
    args = p.parse_args()
    data = load_config()
    if args.action == 'show':
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if args.action == 'set_auto':
        data.setdefault('doubaoBridge', {})['autoBridgeAllowed'] = (args.value == 'true')
        save_config(data)
        print(json.dumps({'ok': True, 'autoBridgeAllowed': data['doubaoBridge']['autoBridgeAllowed']}))


if __name__ == '__main__':
    main()
