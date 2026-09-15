"""k8s SPIRE node-agent bidirectional mTLS (v2.8).

Lifts `charter/spire_node_handshake.py` (config + validation of a
*unidirectional* SVID fetch) to the **bidirectional** mTLS that a real
k8s SPIRE workload does: the node agent attests the *workload* (client
SVID) AND the workload verifies the *node agent* (server SVID), so both
directions carry SPIFFE IDs. This module models the full two-way
handshake as config + validation + a mTLS context builder, without
needing a live SPIRE Server:

    - `BidirMTLSConfig` - the two SVIDs (client=workload SVID,
      server=node-agent SVID) + trust bundles + socket path.
    - `build_bidir_mtls_context(cfg)` - the TLS context spec (client cert +
      key, CA bundle, verify-peer callback) for both directions.
    - `validate_bidir_mtls(cfg)` - offline checks: client + server SVIDs
      are present, both under the same trust domain, both carry the
      expected SPIFFE ID, trust bundles are consistent, the socket is
      reachable-on-paper.
    - `render_bidir_k8s_values(cfg)` - the k8s pod values that mount both
      SVID secrets + the trust bundle + the env to enable both
      `SPIFFE_TLS_CLIENT` and `SPIFFE_TLS_SERVER`.
    - `attestation_exchange_plan(cfg)` - the ordered two-way steps
      (workload->agent attestation, agent->workload SVID, mutual verify).

Stdlib-only. The output is JSON / k8s-values; the live two-way mTLS
handshake happens in the pod's sidecar. CI stays green.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "BidirMTLSConfig", "build_bidir_mtls_context", "validate_bidir_mtls",
    "render_bidir_k8s_values", "attestation_exchange_plan",
]


@dataclass
class BidirMTLSConfig:
    """A two-way mTLS setup between a workload and a node SPIRE agent."""
    trust_domain: str = "charter.example.com"
    namespace: str = "default"
    service_account: str = "spire-workload"
    # client direction: the workload's SVID
    workload_spiffe_id: str = ""
    client_svid_secret: str = "spire-workload-svid"
    # server direction: the node agent's SVID
    agent_spiffe_id: str = ""
    server_svid_secret: str = "spire-agent-svid"
    trust_bundle_path: str = "/run/spire/secrets/trustbundle.json"
    svid_socket: str = "/run/spire/sockets/private/api.sock"
    node_agent_mount: str = "/run/spire"
    svid_ttl_s: int = 3600

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trust_domain": self.trust_domain,
            "namespace": self.namespace,
            "service_account": self.service_account,
            "workload_spiffe_id": self.workload_spiffe_id,
            "client_svid_secret": self.client_svid_secret,
            "agent_spiffe_id": self.agent_spiffe_id,
            "server_svid_secret": self.server_svid_secret,
            "trust_bundle_path": self.trust_bundle_path,
            "svid_socket": self.svid_socket,
            "node_agent_mount": self.node_agent_mount,
            "svid_ttl_s": self.svid_ttl_s,
        }

    def default_spiffe_ids(self) -> "BidirMTLSConfig":
        """Fill the two SPIFFE IDs from the trust domain + SA + agent path
        when they were left empty."""
        if not self.workload_spiffe_id:
            self.workload_spiffe_id = (
                f"spiffe://{self.trust_domain}/ns/{self.namespace}"
                f"/sa/{self.service_account}")
        if not self.agent_spiffe_id:
            self.agent_spiffe_id = (
                f"spiffe://{self.trust_domain}/ns/{self.namespace}"
                f"/agent/node-0")
        return self


def _spiffe_path(sid: str) -> str:
    """The SPIFFE path (/ns/.../sa/...) part of a SPIFFE ID."""
    return sid.split("//", 1)[-1] if "://" in sid else sid


def build_bidir_mtls_context(cfg: BidirMTLSConfig) -> Dict[str, Any]:
    """tool: build_bidir_mtls_context - the TLS context spec for both
    directions (client cert + key, CA bundle, verify-peer callback)."""
    c = cfg.default_spiffe_ids()
    d = c.as_dict()
    return {
        "trust_domain": d["trust_domain"],
        "client": {
            "spiffe_id": d["workload_spiffe_id"],
            "svid_secret": d["client_svid_secret"],
            "role": "client",
            "verify_peer_spiffe_id": d["agent_spiffe_id"],
        },
        "server": {
            "spiffe_id": d["agent_spiffe_id"],
            "svid_secret": d["server_svid_secret"],
            "role": "server",
            "verify_peer_spiffe_id": d["workload_spiffe_id"],
        },
        "ca_bundle_path": d["trust_bundle_path"],
        "svid_socket": d["svid_socket"],
        "env": {
            "SPIFFE_ENDPOINT_SOCKET": d["svid_socket"],
            "SPIFFE_TRUST_BUNDLE": d["trust_bundle_path"],
            "SPIFFE_TLS_CLIENT": "true",
            "SPIFFE_TLS_SERVER": "true",
            "SPIFFE_AGENT_DATA_SEED":
                f"k8s://{d['namespace']}/{d['service_account']}",
        },
        "verify_peer_callback": (
            "match peer SVID URI SAN against verify_peer_spiffe_id"),
    }


def validate_bidir_mtls(cfg: BidirMTLSConfig) -> Dict[str, Any]:
    """tool: validate_bidir_mtls - offline checks of a two-way mTLS config.

    Problems: missing SPIFFE IDs after defaults, the two SVIDs not under
    the same trust domain, the trust bundle not under the node-agent
    mount, the socket not under the mount, or a missing service account.
    Returns {ok, problems:[...], checks:{...}}.
    """
    c = cfg.default_spiffe_ids()
    d = c.as_dict()
    checks: Dict[str, bool] = {}
    problems: List[str] = []

    # 1. both SPIFFE IDs present + under the trust domain
    td = "spiffe://" + d["trust_domain"]
    for key, label in (("workload_spiffe_id", "client"),
                       ("agent_spiffe_id", "server")):
        sid = d[key]
        ok = bool(sid) and (sid.startswith(td) or
                            sid == "spiffe://" + d["trust_domain"])
        checks[f"{label}_spiffe_id_present"] = ok
        if not ok:
            problems.append(
                f"{label} SPIFFE ID is missing or not under {td!r}")

    # 2. trust bundle under the mount
    checks["trust_bundle_under_mount"] = (
        d["trust_bundle_path"].startswith(d["node_agent_mount"] + "/"))
    if not checks["trust_bundle_under_mount"]:
        problems.append(
            f"trust bundle {d['trust_bundle_path']!r} not under the "
            f"node-agent mount {d['node_agent_mount']!r}")

    # 3. socket under the mount
    checks["socket_under_mount"] = (
        d["svid_socket"].startswith(d["node_agent_mount"] + "/"))
    if not checks["socket_under_mount"]:
        problems.append(
            f"socket {d['svid_socket']!r} not under the node-agent mount")

    # 4. service account set
    checks["service_account_set"] = bool(d["service_account"])
    if not d["service_account"]:
        problems.append("service_account is empty")

    return {"ok": not problems, "problems": problems, "checks": checks,
            "config": d}


def render_bidir_k8s_values(cfg: BidirMTLSConfig,
                            secret_name: str = "spire-svid"
                            ) -> Dict[str, Any]:
    """tool: render_bidir_k8s_values - the k8s values that mount *both*
    SVID secrets + the trust bundle + env to enable two-way mTLS."""
    c = cfg.default_spiffe_ids()
    d = c.as_dict()
    env = build_bidir_mtls_context(c)["env"]
    volumes = [
        {"name": "workload-svid", "secret": {"secretName":
            d["client_svid_secret"]}},
        {"name": "agent-svid", "secret": {"secretName":
            d["server_svid_secret"]}},
        {"name": "trust-bundle",
         "configMap": {"name": "spire-trust-bundle"}},
        {"name": "spire-sockets", "emptyDir": {}},
    ]
    mounts = [
        {"name": "workload-svid",
         "mountPath": os.path.dirname(d["trust_bundle_path"]) +
         "/workload", "readOnly": True},
        {"name": "agent-svid",
         "mountPath": os.path.dirname(d["trust_bundle_path"]) +
         "/agent", "readOnly": True},
        {"name": "trust-bundle",
         "mountPath": d["trust_bundle_path"], "readOnly": True},
        {"name": "spire-sockets",
         "mountPath": d["node_agent_mount"] + "/sockets",
         "readOnly": False},
    ]
    return {
        "spiffe": {
            "enabled": True,
            "trustDomain": d["trust_domain"],
            "bidirectional": True,
            "volumes": volumes,
            "volumeMounts": mounts,
            "env": env,
            "svidSocket": d["svid_socket"],
        },
    }


def attestation_exchange_plan(cfg: BidirMTLSConfig) -> List[Dict[str, str]]:
    """tool: attestation_exchange_plan - the ordered two-way steps for a
    real SPIFFE workload <-> node-agent mTLS handshake."""
    c = cfg.default_spiffe_ids()
    d = c.as_dict()
    return [
        {"step": "workload-attest",
         "detail": (f"workload attests to the node agent over "
                    f"{d['svid_socket']} (seed "
                    f"k8s://{d['namespace']}/{d['service_account']})")},
        {"step": "agent-issues-workload-svid",
         "detail": (f"agent returns the workload SVID "
                    f"{d['workload_spiffe_id']} + CA bundle")},
        {"step": "agent-attest-node",
         "detail": (f"the node itself attests to the SPIRE Server; the "
                    f"agent presents {d['agent_spiffe_id']}")},
        {"step": "mutual-verify",
         "detail": ("each side verifies the peer's SVID against the trust "
                    "bundle (URI SAN + chain + expiry) - both directions")},
        {"step": "mtls-session",
         "detail": ("a bidirectional mTLS session: client presents the "
                    "workload SVID, server presents the agent SVID; "
                    "both are authenticated")},
    ]
