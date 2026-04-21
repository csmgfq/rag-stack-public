#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
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


app = FastAPI(
    title='Tailscale Port Proxy Manager',
    version='1.1.0',
    description='Unified management API for tailscale proxy mappings. Supports legacy and /api/v1 paths.',
)

legacy = APIRouter()
v1 = APIRouter(prefix='/api/v1', tags=['v1'])


def _load() -> dict[str, Any]:
    if not CONFIG.exists():
        return {'mappings': []}
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def _save(data: dict[str, Any]) -> None:
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _ctl(action: str) -> Any:
    out = subprocess.check_output(['python3', str(CTL), action], text=True)
    return json.loads(out)


def _health() -> dict[str, Any]:
    return {'status': 'ok', 'api_version': 'v1', 'legacy_compatible': True}


def _status() -> Any:
    return _ctl('status')


def _list_mappings() -> Any:
    return _load()


def _upsert_mapping(mapping: Mapping) -> Any:
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


def _delete_mapping(name: str) -> Any:
    data = _load()
    arr = data.get('mappings', [])
    new_arr = [x for x in arr if x.get('name') != name]
    if len(new_arr) == len(arr):
        raise HTTPException(status_code=404, detail='mapping not found')
    _save({'mappings': new_arr})
    return {'deleted': name}


def _apply_now() -> Any:
    return _ctl('apply')


def _stop_now() -> Any:
    return _ctl('stop')


@legacy.get('/health')
def health_legacy() -> dict[str, Any]:
    return _health()


@legacy.get('/status')
def status_legacy() -> Any:
    return _status()


@legacy.get('/mappings')
def mappings_legacy() -> Any:
    return _list_mappings()


@legacy.post('/mappings')
def upsert_legacy(mapping: Mapping) -> Any:
    return _upsert_mapping(mapping)


@legacy.delete('/mappings/{name}')
def delete_legacy(name: str) -> Any:
    return _delete_mapping(name)


@legacy.post('/apply')
def apply_legacy() -> Any:
    return _apply_now()


@legacy.post('/stop')
def stop_legacy() -> Any:
    return _stop_now()


@v1.get('/health')
def health_v1() -> dict[str, Any]:
    return _health()


@v1.get('/status')
def status_v1() -> Any:
    return _status()


@v1.get('/mappings')
def mappings_v1() -> Any:
    return _list_mappings()


@v1.post('/mappings')
def upsert_v1(mapping: Mapping) -> Any:
    return _upsert_mapping(mapping)


@v1.delete('/mappings/{name}')
def delete_v1(name: str) -> Any:
    return _delete_mapping(name)


@v1.post('/apply')
def apply_v1() -> Any:
    return _apply_now()


@v1.post('/stop')
def stop_v1() -> Any:
    return _stop_now()


app.include_router(legacy)
app.include_router(v1)
