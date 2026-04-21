#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path('/root/tailscale-proxy')
CONFIG = BASE / 'proxies.json'
PID_FILE = BASE / 'socat.pids'
LOG_DIR = BASE / 'logs'


def tailscale_ip() -> str:
    out = subprocess.check_output(['tailscale', 'ip', '-4'], text=True)
    ip = out.strip().splitlines()[0]
    if not ip:
        raise RuntimeError('tailscale IPv4 not found')
    return ip


def load_config() -> dict[str, Any]:
    with CONFIG.open('r', encoding='utf-8') as f:
        return json.load(f)


def stop_all() -> int:
    killed = 0
    if PID_FILE.exists():
        for line in PID_FILE.read_text(encoding='utf-8').splitlines():
            parts = line.split(' ', 1)
            if not parts:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except ProcessLookupError:
                pass
            except PermissionError:
                pass
        PID_FILE.unlink(missing_ok=True)
    for p in [1234, 6333, 6334, 19090, 9401, 13000, 11300]:
        subprocess.run(['pkill', '-f', f'socat TCP-LISTEN:{p},bind='], check=False)
    return killed


def apply() -> list[dict[str, Any]]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stop_all()
    ip = tailscale_ip()
    cfg = load_config()
    mappings = cfg.get('mappings', [])
    started: list[dict[str, Any]] = []
    lines: list[str] = []

    for item in mappings:
        if not item.get('enabled', True):
            continue
        name = str(item['name'])
        lport = int(item['listen_port'])
        thost = str(item['target_host'])
        tport = int(item['target_port'])
        log_path = LOG_DIR / f'{name}.log'
        cmd = [
            'socat',
            f'TCP-LISTEN:{lport},bind={ip},reuseaddr,fork',
            f'TCP:{thost}:{tport}',
        ]
        with log_path.open('ab') as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=lf)
        lines.append(f"{proc.pid} {name} {lport}->{thost}:{tport}")
        started.append({
            'pid': proc.pid,
            'name': name,
            'listen': f'{ip}:{lport}',
            'target': f'{thost}:{tport}',
        })

    PID_FILE.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
    time.sleep(1)
    return started


def status() -> dict[str, Any]:
    ip = tailscale_ip()
    entries: list[dict[str, Any]] = []
    if PID_FILE.exists():
        for line in PID_FILE.read_text(encoding='utf-8').splitlines():
            parts = line.split(' ', 2)
            if len(parts) < 3:
                continue
            pid = int(parts[0])
            name = parts[1]
            route = parts[2]
            alive = Path(f'/proc/{pid}').exists()
            entries.append({'pid': pid, 'name': name, 'route': route, 'alive': alive})
    return {'tailscale_ip': ip, 'entries': entries}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'apply':
        print(json.dumps({'started': apply()}, ensure_ascii=False, indent=2))
        return 0
    if cmd == 'stop':
        print(json.dumps({'killed': stop_all()}, ensure_ascii=False))
        return 0
    if cmd == 'status':
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    print('usage: proxy_ctl.py [apply|stop|status]', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
