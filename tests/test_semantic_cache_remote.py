"""v3.13: SemanticCache distributed/remote backend layer."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from charter import SemanticCache, make_remote_backend, HTTPKeyValueBackend, SemanticCacheBackend
import json
import threading
import urllib.request
import http.server


class _KVStore(http.server.BaseHTTPRequestHandler):
    """Minimal in-memory key-value store over HTTP (the surface the
    HTTPKeyValueBackend speaks)."""
    store = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        key = self.path.split("/kv/")[-1]
        import urllib.parse as _u
        key = _u.unquote(key)
        if key in _KVStore.store:
            body = json.dumps(_KVStore.store[key]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        key = self.path.split("/kv/")[-1]
        import urllib.parse as _u
        key = _u.unquote(key)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _KVStore.store[key] = json.loads(body.decode())
        self.send_response(200)
        self.end_headers()


def _start_server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _KVStore)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_backend_factory_http():
    b = make_remote_backend("http", "http://127.0.0.1:9999")
    assert isinstance(b, HTTPKeyValueBackend)
    assert "http" in b.name()


def test_backend_factory_null_and_unknown():
    n = make_remote_backend("null")
    assert n.get("x") is None
    assert n.name() == "null"
    try:
        make_remote_backend("wat")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_backend_family_aliases_map_to_http():
    for kind in ("redis", "postgres", "memcached", "kv"):
        b = make_remote_backend(kind, "http://127.0.0.1:1")
        assert isinstance(b, HTTPKeyValueBackend), kind


def test_http_backend_live_roundtrip():
    srv, url = _start_server()
    try:
        b = make_remote_backend("http", url)
        cache = SemanticCache(max_entries=4, remote=b)
        # put -> mirrored to remote under the semantic-key hash
        cache.put("q1", {"answer": 42})
        assert _KVStore.store, "remote store empty after put"

        # a cache that uses the SAME backend but has fresh memory (L1) still
        # finds the value via the remote L3 on lookup
        fresh = SemanticCache(max_entries=4, remote=b)
        hit = fresh.get("q1")
        assert hit == {"answer": 42}, f"L3 remote miss: {hit!r}"
        fresh.close()
        cache.close()
    finally:
        srv.shutdown()


def test_http_backend_direct_put_get_roundtrip():
    srv, url = _start_server()
    try:
        b = make_remote_backend("http", url)
        b.put("direct-key", {"v": 1})
        assert b.get("direct-key") == {"v": 1}
        assert b.get("missing-key") is None
        b.close()
    finally:
        srv.shutdown()


def test_http_backend_offline_degrades_to_miss():
    # unroutable port -> every op silently degrades, never raises
    b = make_remote_backend("http", "http://127.0.0.1:1", timeout_s=0.3)
    assert b.get("x") is None
    b.put("x", 1)  # must not raise
    cache = SemanticCache(max_entries=4, remote=b)
    cache.put("local-only", 7)
    assert cache.get("local-only") == 7
    cache.close()


def test_cache_stats_expose_remote():
    cache = SemanticCache(max_entries=4, remote=make_remote_backend("null"))
    s = cache.stats()
    assert s["remote_enabled"] is True
    assert s["remote"] == "null"
    cache.close()
    s2 = cache.stats()
    assert s2["remote_enabled"] is False
    assert s2["remote"] is None
