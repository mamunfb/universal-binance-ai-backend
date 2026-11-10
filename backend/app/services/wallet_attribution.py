from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse


ALLOWED_LABELS = {"exchange", "fund", "market_maker", "protocol_treasury", "smart_money", "whale", "unknown"}
ALLOWED_STATUSES = {"unverified", "pending_review", "verified", "rejected"}


def load_wallet_registry(raw: str, chain_id: int) -> dict[str, Any]:
    """Load operator-supplied wallet labels with explicit provenance; never infer identities."""
    if not raw.strip():
        return {
            "status": "EMPTY",
            "chain_id": chain_id,
            "wallet_count": 0,
            "wallets": [],
            "warning": "No wallet identities are configured. No address is assumed to belong to an exchange, fund, whale, or smart-money entity.",
        }
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("EVM_WALLET_REGISTRY must be valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError("EVM_WALLET_REGISTRY must be a JSON array")
    wallets = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Every wallet registry entry must be an object")
        address = item.get("address")
        if not isinstance(address, str) or len(address) != 42 or not address.startswith("0x"):
            raise ValueError("Every registry entry requires a valid 0x-prefixed EVM address")
        try:
            int(address[2:], 16)
        except ValueError as exc:
            raise ValueError("Registry contains a non-hexadecimal address") from exc
        normalized = address.lower()
        if normalized in seen:
            raise ValueError(f"Duplicate registry address: {normalized}")
        seen.add(normalized)
        label = item.get("label", "unknown")
        status = item.get("verification_status", "unverified")
        if label not in ALLOWED_LABELS:
            raise ValueError(f"Unsupported wallet label: {label}")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported verification status: {status}")
        evidence_url = item.get("evidence_url")
        evidence_note = item.get("evidence_note")
        if status == "verified":
            parsed = urlparse(evidence_url or "")
            if parsed.scheme != "https" or not parsed.netloc or not isinstance(evidence_note, str) or not evidence_note.strip():
                raise ValueError("Verified entries require an HTTPS evidence_url and a non-empty evidence_note")
        wallets.append({
            "address": normalized,
            "label": label,
            "entity_name": item.get("entity_name"),
            "verification_status": status,
            "evidence_url": evidence_url,
            "evidence_note": evidence_note,
            "source_published_at": item.get("source_published_at"),
            "last_reviewed_at": item.get("last_reviewed_at"),
            "chain_id": chain_id,
            "is_operator_supplied": True,
        })
    return {
        "status": "COMPLETED",
        "chain_id": chain_id,
        "wallet_count": len(wallets),
        "verified_count": sum(item["verification_status"] == "verified" for item in wallets),
        "unverified_count": sum(item["verification_status"] != "verified" for item in wallets),
        "wallets": wallets,
        "warning": "Registry labels are operator-supplied. A verified status means supporting evidence was supplied and reviewed by the operator; this service does not independently authenticate the publisher or prove beneficial ownership.",
    }


def annotate_wallet_addresses(addresses: list[str], registry: dict[str, Any]) -> list[dict[str, Any]]:
    indexed = {item["address"]: item for item in registry.get("wallets", [])}
    result = []
    for address in addresses:
        entry = indexed.get(address.lower())
        result.append({
            "address": address.lower(),
            "label": entry["label"] if entry else "unknown",
            "entity_name": entry.get("entity_name") if entry else None,
            "verification_status": entry["verification_status"] if entry else "unverified",
            "evidence_url": entry.get("evidence_url") if entry else None,
            "evidence_note": entry.get("evidence_note") if entry else None,
        })
    return result
