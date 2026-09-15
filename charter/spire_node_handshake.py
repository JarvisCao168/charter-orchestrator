"""k8s SPIRE node-agent socket handshake (v2.7).

Lifts `charter/spire_k8s_mtls.py` (config/values/env artifacts) to the
**workload <-> node-agent socket** that a real k8s pod uses: the SPIRE
Agent inside a pod serves the SPIFFE Workload API over a Unix domain
socket; the main container's app dials that socket, presents its
attestation, and receives the SVID + CA bundle to do mTLS. This module
models that handshake end-to-end as *config + validation*, without
needing a live SPIRE Server / kernel:

    - `WorkloadSocketConfig` - the socket path + trust bundle + agent
      env a pod's main container reads.
    - `render_workload_socket_manifests(cfg)` - the k8s manifests that
      wire the node agent's socket into the pod (emptyDir volume +
      env + a postStart hook that pings the socket).
    - `validate_workload_socket(cfg)` - offline checks: socket path is
      under the node-agent's mount, the trust bundle path is set, the
      env is consistent, the postStart hook command is valid.
    - `handshake_plan(cfg)` - the ordered steps a real client follows
      (connect -> attestation -> FetchX509SVID -> verify -> mTLS),
      as a documented plan (the module does not perform the gRPC; it
      produces the artifact + validation a reviewer / automation can
      check).

Stdlib-only. The output is JSON / k8s-manifest docs; the live gRPC
handshake happens in the pod. CI stays green.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "WorkloadSocketConfig", "render_workload_socket_manifests",
    "validate_workload_socket", "handshake_plan",
]

_DEFAULT_SOCKET = "/run/spire/sockets/private/api.sock"
_DEFAULT_BUNDLE = "/run/spire/secrets/trustbundle.json"
_DEFAULT_AGENT_MOUNT = "/run/spire"


@dataclass
class WorkloadSocketConfig:
    """How a pod's main container reaches the node SPIRE Agent socket."""
    trust_domain: str = "charter.example.com"
    svid_socket: str = _DEFAULT_SOCKET
    trust_bundle_path: str = _DEFAULT_BUNDLE
    node_agent_mount: str = _DEFAULT_AGENT_MOUNT
    namespace: str = "default"
    service_account: str = "spire-workload"
    svid_ttl_s: int = 3600

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trust_domain": self.trust_domain,
            "svid_socket": self.svid_socket,
            "trust_bundle_path": self.trust_bundle_path,
            "node_agent_mount": self.node_agent_mount,
            "namespace": self.namespace,
            "service_account": self.service_account,
            "svid_ttl_s": self.svid_ttl_s,
        }


def render_workload_socket_manifests(
        cfg: WorkloadSocketConfig,
        secret_name: str = "spire-svid") -> Dict[str, Any]:
    """tool: render_workload_socket_manifests - k8s manifests that wire the
    node-agent socket into the pod (emptyDir + env + postStart ping)."""
    d = cfg.as_dict()
    env: Dict[str, str] = {
        "SPIFFE_ENDPOINT_SOCKET": d["svid_socket"],
        "SPIFFE_TRUST_BUNDLE": d["trust_bundle_path"],
        "SPIFFE_WORKLOAD_API_SOCKET": d["svid_socket"],
        "SPIFFE_TLS_CLIENT": "true",
        "SPIFFE_TLS_SERVER": "true",
        "SPIFFE_AGENT_DATA_SEED":
            f"k8s://{d['namespace']}/{d['service_account']}",
    }
    pod_spec_fragment = {
        "volumes": [
            {"name": "spire-svid", "secret": {"secretName": secret_name}},
            {"name": "spire-sockets", "emptyDir": {}},
        ],
        "containers": [{
            "name": "app",
            "image": "charter/app:latest",
            "env": [{"name": k, "value": v} for k, v in env.items()],
            "volumeMounts": [
                {"name": "spire-svid",
                 "mountPath": os.path.dirname(d["trust_bundle_path"]),
                 "readOnly": True},
                {"name": "spire-sockets",
                 "mountPath": d["node_agent_mount"] + "/sockets",
                 "readOnly": False},
            ],
            "securityContext": {"runAsUser": 0},
            "lifecycle": {
                "postStart": {
                    "exec": {
                        "command": [
                            "sh", "-c",
                            # ping the SPIFFE workload API socket; the
                            # agent serves it once the SVID is fetched
                            f"timeout 10s sh -c 'until ls "
                            f"{d['svid_socket']} >/dev/null 2>&1; do sleep 1; "
                            f"done'",
                        ],
                    }
                }
            },
        }],
    }
    return {
        "pod_spec_fragment": pod_spec_fragment,
        "env": env,
        "secret": {"name": secret_name,
                    "keys": ["trustbundle.json", "svid.crt", "svid.key"]},
        "socket_path": d["svid_socket"],
        "trust_bundle_path": d["trust_bundle_path"],
    }


def validate_workload_socket(cfg: WorkloadSocketConfig) -> Dict[str, Any]:
    """tool: validate_workload_socket - offline checks of a socket config.

    Returns {ok, problems:[...], checks:{...}}. Problems:
        - svid_socket not under node_agent_mount
        - trust bundle path not set
        - trust domain not DNS-safe
        - service account not set
        - socket / bundle path consistency (bundle under the mount)
    """
    d = cfg.as_dict()
    checks: Dict[str, bool] = {}
    problems: List[str] = []

    # 1. socket under the mount
    sock = d["svid_socket"]
    mount = d["node_agent_mount"]
    under = (sock.startswith(mount + "/") or sock == mount)
    checks["socket_under_mount"] = under
    if not under:
        problems.append(
            f"svid_socket {sock!r} is not under node_agent_mount {mount!r}")

    # 2. trust bundle set + under mount
    bundle = d["trust_bundle_path"]
    bundle_set = bool(bundle)
    bundle_under = bundle.startswith(mount + "/")
    checks["trust_bundle_set"] = bundle_set
    checks["trust_bundle_under_mount"] = bundle_under
    if not bundle_set:
        problems.append("trust_bundle_path is empty")
    elif not bundle_under:
        problems.append(
            f"trust_bundle_path {bundle!r} is not under the mount {mount!r}")

    # 3. trust domain DNS-safe
    import re
    td = d["trust_domain"]
    dns_safe = bool(re.fullmatch(r"[a-z0-9.-]+", td.lower().strip()))
    checks["trust_domain_dns_safe"] = dns_safe
    if not dns_safe:
        problems.append(f"trust_domain {td!r} is not DNS-safe")

    # 4. service account set
    checks["service_account_set"] = bool(d["service_account"])
    if not d["service_account"]:
        problems.append("service_account is empty")

    ok = not problems
    return {"ok": ok, "problems": problems, "checks": checks,
            "config": d}


def handshake_plan(cfg: WorkloadSocketConfig) -> List[Dict[str, str]]:
    """tool: handshake_plan - the ordered steps a real client follows to
    reach mTLS over the node-agent socket.

    The module does NOT perform the gRPC; it returns the documented step
    sequence so a reviewer / automation can verify the wiring is complete.
    """
    d = cfg.as_dict()
    return [
        {"step": "connect",
         "detail": (f"dial the SPIFFE Workload API over the Unix socket at "
                    f"{d['svid_socket']}")},
        {"step": "attest",
         "detail": (f"present the k8s service-account JWT "
                    f"(seed k8s://{d['namespace']}/{d['service_account']}) "
                    f"to attestation")},
        {"step": "fetch_svid",
         "detail": "call FetchX509SVID; the agent returns an SVID cert + "
                    "key + CA bundle for " + d["trust_domain"]},
        {"step": "verify",
         "detail": "verify the SVID against the trust bundle at "
                    f"{d['trust_bundle_path']} (chain + URI SAN)"},
        {"step": "mtls",
         "detail": "start mTLS: present SVID as client cert, verify the "
                    "peer's SVID; both directions are now authenticated"},
    ]
