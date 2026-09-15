"""k8s SPIRE Agent mTLS (v2.6).

Lifts `charter/spiffe_attestation.py` (attestation *request* shape + local
fallback) to the **real k8s workload path**: a pod running a *SPIRE Agent*
does the attestation locally (k8s SA JWT + projected token) and serves the
SVID over the agent's local Unix socket; a sidecar / main container then
presents that SVID to peers over mTLS. This module models:

    - `K8SSPIREAgentConfig` - the SPIRE Agent's k8s attestation config
      (service_account, namespace, workload JWT path, trust domain,
      `agents` registry for the SPIRE Server).
    - `render_spire_agent_config(cfg)` - the JSON config a real
      `spire-agent` on a node would read (`agent: {data_seeds,
      k8s: {service_account, namespace}}` shape), ready to write to
      `/run/spire/config/agent.json`.
    - `render_agent_values(cfg, svid_uri)` - the k8s **values** that mount
      the SVID Unix socket + CA bundle into the pod so the app can do
      mTLS (secret / projected-token volumes + env).
    - `mtls_env(config)` - the `SPIFFE_ENDPOINT_SOCKET` / `SPIFFE_TRUST_BUNDLE`
      env vars + the `SPIFFE_TLS_SERVER` / `SPIFFE_TLS_CLIENT` flags a
      SPIFFE-enabled app reads to enable mTLS.

Stdlib-only. No k8s / gRPC needed: the output is pure JSON / k8s-values
docs. The *live* mTLS handshake happens in the pod's sidecar; this module
only produces the config artifacts that wire it up, so CI stays green.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "K8SSPIREAgentConfig", "render_spire_agent_config",
    "render_agent_values", "mtls_env",
]


@dataclass
class K8SSPIREAgentConfig:
    """Config for a k8s SPIRE Agent doing workload attestation."""
    trust_domain: str = "charter.example.com"
    namespace: str = "default"
    service_account: str = "spire-workload"
    workload_jwt_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    svid_socket: str = "/run/spire/sockets/private/api.sock"
    trust_bundle_path: str = "/run/spire/secrets/trustbundle.json"
    data_seeds: List[str] = field(default_factory=lambda: ["k8s-service-account"])
    attestation_type: str = "k8s"
    svid_ttl_s: int = 3600

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trust_domain": self.trust_domain,
            "namespace": self.namespace,
            "service_account": self.service_account,
            "workload_jwt_path": self.workload_jwt_path,
            "svid_socket": self.svid_socket,
            "trust_bundle_path": self.trust_bundle_path,
            "data_seeds": self.data_seeds,
            "attestation_type": self.attestation_type,
            "svid_ttl_s": self.svid_ttl_s,
        }


def render_spire_agent_config(cfg: K8SSPIREAgentConfig,
                              spire_server_url: str = "spire-server:8091") -> Dict[str, Any]:
    """tool: render_spire_agent_config - the JSON config a real spire-agent
    reads (`agent.data_seeds`, `agent.k8s`)."""
    d = cfg.as_dict()
    return {
        "agent": {
            "data_seeds": [f"k8s://{d['namespace']}/{d['service_account']}"],
            "k8s": {
                "service_account": d["service_account"],
                "namespace": d["namespace"],
            },
        },
        "server": {
            "address": spire_server_url,
            "trust_bundle_path": d["trust_bundle_path"],
        },
        "entries": [{
            "spiffe_id": f"spiffe://{d['trust_domain']}/ns/{d['namespace']}/sa/{d['service_account']}",
            "parent_id": "k8s-service-account",
            "selector": (
                "k8s:ns=" + d["namespace"] +
                ";sa=" + d["service_account"]),
            "ttl": f"{d['svid_ttl_s']}s",
        }],
        "trust_domain": d["trust_domain"],
    }


def render_agent_values(cfg: K8SSPIREAgentConfig,
                        secret_name: str = "spire-svid",
                        ) -> Dict[str, Any]:
    """tool: render_agent_values - the k8s *values* that mount the SVID
    socket + trust bundle into the pod for mTLS.

    Returns a Helm-style values dict (volumes + volumeMounts + env +
    projected serviceaccount token) ready to feed a k8s Deployment / Helm
    chart.
    """
    d = cfg.as_dict()
    return {
        "spiffe": {
            "enabled": True,
            "trustDomain": d["trust_domain"],
            "secretName": secret_name,
            "volumes": [
                {
                    "name": "spire-workload-jwt",
                    "projected": {
                        "sources": [{
                            "serviceAccountToken": {
                                "audience": d["trust_domain"],
                                "expirationSeconds": d["svid_ttl_s"],
                                "path": "token",
                            },
                        }],
                    },
                },
            ],
            "volumeMounts": [
                {"name": "spire-workload-jwt",
                 "mountPath": d["workload_jwt_path"], "readOnly": True},
                {"name": secret_name,
                 "mountPath": os.path.dirname(d["trust_bundle_path"]),
                 "readOnly": True},
            ],
            "env": mtls_env(cfg),
            "svidSocket": d["svid_socket"],
        },
    }


def mtls_env(cfg: K8SSPIREAgentConfig,
             server: bool = True, client: bool = True
             ) -> Dict[str, str]:
    """The env vars a SPIFFE-enabled app reads to enable mTLS."""
    d = cfg.as_dict()
    env: Dict[str, str] = {
        "SPIFFE_ENDPOINT_SOCKET": d["svid_socket"],
        "SPIFFE_TRUST_BUNDLE": d["trust_bundle_path"],
        "SPIFFE_WORKLOAD_API_SOCKET": d["svid_socket"],
        "SPIFFE_AGENT_DATA_SEED":
            f"k8s://{d['namespace']}/{d['service_account']}",
    }
    if server:
        env["SPIFFE_TLS_SERVER"] = "true"
    if client:
        env["SPIFFE_TLS_CLIENT"] = "true"
    return env


