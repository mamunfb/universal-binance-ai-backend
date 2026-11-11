from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse


ALLOWED_LABELS = {"exchange", "fund", "market_maker", "protocol_treasury", "smart_money", "whale", "unknown"}
ALLOWED_STATUSES = {"unverified", "pending_review", "verified", "rejected"}
ALLOWED_FIELDS = {
    "address", "label", "verification_status", "entity_name", "evidence_url",
    "evidence_note", "source_published_at", "last_reviewed_at",
}
_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _validate_address(address: Any) -> str:
    if not isinstance(address, str) or not _EVM_ADDRESS.fullmatch(address):
        raise ValueError("Every wallet address must be a 0x-prefixed 20-byte hexadecimal EVM address")
    return address.lower()


def load_wallet_registry(raw: str, chain_id: int) -> dict[str, Any]:
    """Load operator-supplied wallet labels with explicit provenance; never infer identities."""
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id < 0:
        raise ValueError("chain_id must be a non-negative integer")
    if not isinstance(raw, str):
        raise ValueError("EVM_WALLET_REGISTRY must be a JSON string")
    if not raw.strip():
        return {
            "status": "EMPTY", "chain_id": chain_id, "wallet_count": 0,
            "wallets": [],
            "warning": "No wallet identities are configured. No address is assumed to belong to an exchange, fund, whale, or smart-money entity.",
        }
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("EVM_WALLET_REGISTRY must be valid JSON") from exc
    if not isinstance(entries, list):
        raise ValueError("EVM_WALLET_REGISTRY must be a JSON array")
    if not entries:
        return {
            "status": "EMPTY", "chain_id": chain_id, "wallet_count": 0,
            "verified_count": 0, "unverified_count": 0, "wallets": [],
            "warning": "No wallet identities are configured. No address is assumed to belong to an exchange, fund, whale, or smart-money entity.",
        }

    wallets = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Every wallet registry entry must be an object")
        unknown_fields = set(item) - ALLOWED_FIELDS
        if unknown_fields:
            raise ValueError(f"Unsupported wallet registry fields: {', '.join(sorted(unknown_fields))}")
        normalized = _validate_address(item.get("address"))
        if normalized in seen:
            raise ValueError(f"Duplicate registry address: {normalized}")
        seen.add(normalized)

        label = item.get("label", "unknown")
        status = item.get("verification_status", "unverified")
        if not isinstance(label, str) or label not in ALLOWED_LABELS:
            raise ValueError(f"Unsupported wallet label: {label}")
        if not isinstance(status, str) or status not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported verification status: {status}")

        entity_name = item.get("entity_name")
        evidence_url = item.get("evidence_url")
        evidence_note = item.get("evidence_note")
        if entity_name is not None and (
            not isinstance(entity_name, str) or not entity_name.strip() or len(entity_name) > 200
        ):
            raise ValueError("entity_name must be a non-empty string of at most 200 characters")
        if evidence_url is not None and not isinstance(evidence_url, str):
            raise ValueError("evidence_url must be a string")
        if evidence_note is not None and (
            not isinstance(evidence_note, str) or len(evidence_note) > 2000
        ):
            raise ValueError("evidence_note must be a string of at most 2000 characters")
        for field in ("source_published_at", "last_reviewed_at"):
            value = item.get(field)
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 64
            ):
                raise ValueError(f"{field} must be a non-empty string of at most 64 characters")

        if status == "verified":
            try:
                parsed = urlparse(evidence_url or "")
                valid_url = (
                    parsed.scheme == "https" and bool(parsed.hostname)
                    and parsed.username is None and parsed.password is None
                    and parsed.port in (None, 443, 8443, 9443)
                )
            except ValueError:
                valid_url = False
            if not valid_url or not isinstance(evidence_note, str) or not evidence_note.strip():
                raise ValueError("Verified entries require an HTTPS evidence_url and a non-empty evidence_note")

        wallets.append({
            "address": normalized, "label": label, "entity_name": entity_name,
            "verification_status": status, "evidence_url": evidence_url,
            "evidence_note": evidence_note,
            "source_published_at": item.get("source_published_at"),
            "last_reviewed_at": item.get("last_reviewed_at"),
            "chain_id": chain_id, "is_operator_supplied": True,
        })

    return {
        "status": "COMPLETED", "chain_id": chain_id, "wallet_count": len(wallets),
        "verified_count": sum(item["verification_status"] == "verified" for item in wallets),
        "unverified_count": sum(item["verification_status"] != "verified" for item in wallets),
        "wallets": wallets,
        "warning": "Registry labels are operator-supplied. A verified status means supporting evidence was supplied and reviewed by the operator; this service does not independently authenticate the publisher or prove beneficial ownership.",
    }


def annotate_wallet_addresses(addresses: list[str], registry: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(addresses, list):
        raise ValueError("addresses must be a list")
    if not isinstance(registry, dict) or not isinstance(registry.get("wallets", []), list):
        raise ValueError("registry must contain a wallet list")
    normalized_addresses = [_validate_address(address) for address in addresses]
    indexed = {item["address"]: item for item in registry.get("wallets", [])}
    result = []
    for address in normalized_addresses:
        entry = indexed.get(address)
        result.append({
            "address": address,
            "label": entry["label"] if entry else "unknown",
            "entity_name": entry.get("entity_name") if entry else None,
            "verification_status": entry["verification_status"] if entry else "unverified",
            "evidence_url": entry.get("evidence_url") if entry else None,
            "evidence_note": entry.get("evidence_note") if entry else None,
        })
    return result
