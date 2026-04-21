#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = os.environ.get("FNOS_EXPORTER_HOST", "127.0.0.1")
PORT = int(os.environ.get("FNOS_EXPORTER_PORT", "9402"))
CONTAINER_SSH = os.environ.get("CONTAINER_SSH", "root@127.0.0.1")
CONTAINER_SSH_PORT = os.environ.get("CONTAINER_SSH_PORT", "50001")
FNOS_HOST = os.environ.get("FNOS_HOST", "100.109.127.77")
FNOS_PORT = int(os.environ.get("FNOS_PORT", "22"))
SERVER_BACKUPS_ROOT = os.environ.get("SERVER_BACKUPS_ROOT", "/home/jiangzhiming/backups")
CONTAINER_BACKUPS_ROOT = os.environ.get("CONTAINER_BACKUPS_ROOT", "/root/backups")
FNOS_PRIMARY_ROOT = os.environ.get("FNOS_PRIMARY_ROOT", "/vol2/1000/backups/rag-stack")
FNOS_MIRROR_ROOT = os.environ.get("FNOS_MIRROR_ROOT", "/vol02/1000-1-9025b335/rag-stack-backups")

CACHE = {"ts": 0.0, "text": ""}
CACHE_TTL_SECONDS = int(os.environ.get("FNOS_EXPORTER_CACHE_TTL", "30"))


def sh(cmd, timeout=8):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def labels_text(labels):
    if not labels:
        return ""
    parts = []
    for k, v in labels.items():
        esc = str(v).replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'{k}="{esc}"')
    return "{" + ",".join(parts) + "}"


def add(lines, name, value, labels=None):
    if value is None:
        return
    if isinstance(value, bool):
        value = 1 if value else 0
    lines.append(f"{name}{labels_text(labels or {})} {value}")


def latest_backup_stats_local(root):
    p = Path(root)
    if not p.exists():
        return None
    dirs = [d for d in p.iterdir() if d.is_dir()]
    if not dirs:
        return None
    latest = max(dirs, key=lambda d: d.stat().st_mtime)
    size = 0
    files = 0
    for c in latest.rglob("*"):
        if c.is_file():
            files += 1
            try:
                size += c.stat().st_size
            except Exception:
                pass
    return {"name": latest.name, "mtime": int(latest.stat().st_mtime), "size": size, "files": files}


def latest_backup_stats_container():
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p", str(CONTAINER_SSH_PORT), CONTAINER_SSH,
        "python3 - <<'PY'\n"
        "import json, pathlib\n"
        f"root=pathlib.Path('{CONTAINER_BACKUPS_ROOT}')\n"
        "if not root.exists():\n"
        "    print(json.dumps({'ok':0}))\n"
        "    raise SystemExit(0)\n"
        "dirs=[d for d in root.iterdir() if d.is_dir()]\n"
        "if not dirs:\n"
        "    print(json.dumps({'ok':0}))\n"
        "    raise SystemExit(0)\n"
        "latest=max(dirs,key=lambda d:d.stat().st_mtime)\n"
        "size=0\n"
        "files=0\n"
        "for c in latest.rglob('*'):\n"
        "    if c.is_file():\n"
        "        files += 1\n"
        "        try:\n"
        "            size += c.stat().st_size\n"
        "        except Exception:\n"
        "            pass\n"
        "print(json.dumps({'ok':1,'name':latest.name,'mtime':int(latest.stat().st_mtime),'size':size,'files':files}))\n"
        "PY"
    ]
    rc, out, _ = sh(cmd, timeout=8)
    if rc != 0 or not out:
        return None
    try:
        obj = json.loads(out.splitlines()[-1])
        if obj.get("ok") != 1:
            return None
        return obj
    except Exception:
        return None


def latest_backup_stats_fnos(path):
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p", str(CONTAINER_SSH_PORT), CONTAINER_SSH,
        f"ssh -o BatchMode=yes -o ConnectTimeout=5 admin@{FNOS_HOST} "
        f"\"python3 - <<'PY'\n"
        "import json, pathlib\n"
        f"root=pathlib.Path('{path}')\n"
        "if not root.exists():\n"
        "    print(json.dumps({'ok':0}))\n"
        "    raise SystemExit(0)\n"
        "dirs=[d for d in root.iterdir() if d.is_dir()]\n"
        "if not dirs:\n"
        "    print(json.dumps({'ok':0}))\n"
        "    raise SystemExit(0)\n"
        "latest=max(dirs,key=lambda d:d.stat().st_mtime)\n"
        "size=0\n"
        "files=0\n"
        "for c in latest.rglob('*'):\n"
        "    if c.is_file():\n"
        "        files += 1\n"
        "        try:\n"
        "            size += c.stat().st_size\n"
        "        except Exception:\n"
        "            pass\n"
        "print(json.dumps({'ok':1,'name':latest.name,'mtime':int(latest.stat().st_mtime),'size':size,'files':files}))\n"
        "PY\""
    ]
    rc, out, _ = sh(cmd, timeout=12)
    if rc != 0 or not out:
        return None
    try:
        obj = json.loads(out.splitlines()[-1])
        if obj.get("ok") != 1:
            return None
        return obj
    except Exception:
        return None


def net_stats_host():
    try:
        content = Path("/proc/net/dev").read_text(encoding="utf-8")
    except Exception:
        return []
    return parse_net_dev(content)


def net_stats_container():
    rc, out, _ = sh([
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p", str(CONTAINER_SSH_PORT), CONTAINER_SSH,
        "cat /proc/net/dev"
    ], timeout=6)
    if rc != 0:
        return []
    return parse_net_dev(out)


def parse_net_dev(content):
    rows = []
    for line in content.splitlines()[2:]:
        if ":" not in line:
            continue
        iface, data = line.split(":", 1)
        iface = iface.strip()
        parts = data.split()
        if len(parts) < 16:
            continue
        rows.append({
            "iface": iface,
            "rx_bytes": int(parts[0]),
            "rx_packets": int(parts[1]),
            "tx_bytes": int(parts[8]),
            "tx_packets": int(parts[9]),
        })
    return rows


def probe_fnos_tcp_from_container():
    rc, out, _ = sh([
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p", str(CONTAINER_SSH_PORT), CONTAINER_SSH,
        "python3 - <<'PY'\n"
        "import socket, time\n"
        f"host='{FNOS_HOST}'\n"
        f"port={FNOS_PORT}\n"
        "s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n"
        "s.settimeout(2.0)\n"
        "t=time.time()\n"
        "ok=0\n"
        "lat=0.0\n"
        "try:\n"
        "    s.connect((host,port)); ok=1; lat=time.time()-t\n"
        "except Exception:\n"
        "    ok=0; lat=0.0\n"
        "finally:\n"
        "    s.close()\n"
        "print(f'{ok} {lat}')\n"
        "PY"
    ], timeout=8)
    if rc != 0 or not out:
        return 0, 0.0
    parts = out.split()
    if len(parts) < 2:
        return 0, 0.0
    try:
        return int(float(parts[0])), float(parts[1])
    except Exception:
        return 0, 0.0


def collect_metrics_text():
    now = int(time.time())
    lines = [
        "# HELP rag_fnos_tcp_up FNOS TCP reachability from container network path",
        "# TYPE rag_fnos_tcp_up gauge",
        "# HELP rag_fnos_tcp_latency_seconds FNOS TCP connect latency seconds",
        "# TYPE rag_fnos_tcp_latency_seconds gauge",
        "# HELP rag_backup_latest_timestamp_seconds Latest backup folder mtime",
        "# TYPE rag_backup_latest_timestamp_seconds gauge",
        "# HELP rag_backup_latest_size_bytes Latest backup folder size bytes",
        "# TYPE rag_backup_latest_size_bytes gauge",
        "# HELP rag_backup_latest_files_total Latest backup folder file count",
        "# TYPE rag_backup_latest_files_total gauge",
        "# HELP rag_network_rx_bytes_total RX bytes by scope/interface",
        "# TYPE rag_network_rx_bytes_total counter",
        "# HELP rag_network_tx_bytes_total TX bytes by scope/interface",
        "# TYPE rag_network_tx_bytes_total counter",
        "# HELP rag_network_rx_packets_total RX packets by scope/interface",
        "# TYPE rag_network_rx_packets_total counter",
        "# HELP rag_network_tx_packets_total TX packets by scope/interface",
        "# TYPE rag_network_tx_packets_total counter",
        "# HELP rag_transfer_exporter_unix_time Exporter unix timestamp",
        "# TYPE rag_transfer_exporter_unix_time gauge",
    ]

    add(lines, "rag_transfer_exporter_unix_time", now)

    up, lat = probe_fnos_tcp_from_container()
    add(lines, "rag_fnos_tcp_up", up, {"target": f"{FNOS_HOST}:{FNOS_PORT}"})
    add(lines, "rag_fnos_tcp_latency_seconds", lat, {"target": f"{FNOS_HOST}:{FNOS_PORT}"})

    snapshots = [
        ("server_local", latest_backup_stats_local(SERVER_BACKUPS_ROOT)),
        ("container_local", latest_backup_stats_container()),
        ("fnos_primary", latest_backup_stats_fnos(FNOS_PRIMARY_ROOT)),
        ("fnos_mirror", latest_backup_stats_fnos(FNOS_MIRROR_ROOT)),
    ]

    for scope, st in snapshots:
        if not st:
            add(lines, "rag_backup_latest_timestamp_seconds", 0, {"scope": scope})
            add(lines, "rag_backup_latest_size_bytes", 0, {"scope": scope})
            add(lines, "rag_backup_latest_files_total", 0, {"scope": scope})
            continue
        labels = {"scope": scope, "tag": st.get("name", "")}
        add(lines, "rag_backup_latest_timestamp_seconds", st.get("mtime", 0), labels)
        add(lines, "rag_backup_latest_size_bytes", st.get("size", 0), labels)
        add(lines, "rag_backup_latest_files_total", st.get("files", 0), labels)

    for row in net_stats_host():
        labels = {"scope": "host", "iface": row["iface"]}
        add(lines, "rag_network_rx_bytes_total", row["rx_bytes"], labels)
        add(lines, "rag_network_tx_bytes_total", row["tx_bytes"], labels)
        add(lines, "rag_network_rx_packets_total", row["rx_packets"], labels)
        add(lines, "rag_network_tx_packets_total", row["tx_packets"], labels)

    for row in net_stats_container():
        labels = {"scope": "container", "iface": row["iface"]}
        add(lines, "rag_network_rx_bytes_total", row["rx_bytes"], labels)
        add(lines, "rag_network_tx_bytes_total", row["tx_bytes"], labels)
        add(lines, "rag_network_rx_packets_total", row["rx_packets"], labels)
        add(lines, "rag_network_tx_packets_total", row["tx_packets"], labels)

    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ["/", "/metrics"]:
            self.send_response(404)
            self.end_headers()
            return

        now = time.time()
        if now - CACHE["ts"] > CACHE_TTL_SECONDS or not CACHE["text"]:
            CACHE["text"] = collect_metrics_text()
            CACHE["ts"] = now

        body = CACHE["text"].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    srv = HTTPServer((HOST, PORT), Handler)
    print(f"fnos_transfer_exporter listening on {HOST}:{PORT}")
    srv.serve_forever()
