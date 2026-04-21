#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE = Path('/root/tailscale-proxy')
CONFIG = BASE / 'proxies.json'
CTL = BASE / 'proxy_ctl.py'


class Mapping(BaseModel):
    name: str = Field(min_length=1)
    listen_port: int = Field(ge=1, le=65535)
    target_host: str
    target_port: int = Field(ge=1, le=65535)
    enabled: bool = True


app = FastAPI(title='Tailscale Port Proxy Manager', version='1.0.0')


def _load() -> dict[str, Any]:
    if not CONFIG.exists():
        return {'mappings': []}
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def _save(data: dict[str, Any]) -> None:
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _ctl(action: str) -> Any:
    out = subprocess.check_output(['python3', str(CTL), action], text=True)
    return json.loads(out)


@app.get('/health')
def health() -> dict[str, Any]:
    return {'status': 'ok'}


@app.get('/status')
def status() -> Any:
    return _ctl('status')


@app.get('/mappings')
def list_mappings() -> Any:
    return _load()


@app.post('/mappings')
def upsert_mapping(mapping: Mapping) -> Any:
    data = _load()
    arr = data.get('mappings', [])
    for idx, item in enumerate(arr):
        if item.get('name') == mapping.name:
            arr[idx] = mapping.model_dump()
            _save({'mappings': arr})
            return {'updated': mapping.name}
    arr.append(mapping.model_dump())
    _save({'mappings': arr})
    return {'created': mapping.name}


@app.delete('/mappings/{name}')
def delete_mapping(name: str) -> Any:
    data = _load()
    arr = data.get('mappings', [])
    new_arr = [x for x in arr if x.get('name') != name]
    if len(new_arr) == len(arr):
        raise HTTPException(status_code=404, detail='mapping not found')
    _save({'mappings': new_arr})
    return {'deleted': name}


@app.post('/apply')
def apply_now() -> Any:
    return _ctl('apply')


@app.post('/stop')
def stop_now() -> Any:
    return _ctl('stop')
