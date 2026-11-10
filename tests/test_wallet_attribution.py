import pytest

from app.services.wallet_attribution import load_wallet_registry, annotate_wallet_addresses

ADDR_A = "0x" + "1" * 40
ADDR_B = "0x" + "2" * 40


def test_empty_registry_never_infers_wallet_identity():
    result = load_wallet_registry("[]", 1)
    assert result["status"] == "EMPTY"
    assert result["wallet_count"] == 0
    row = annotate_wallet_addresses([ADDR_A], result)[0]
    assert row["label"] == "unknown"
    assert row["verification_status"] == "unverified"


def test_verified_wallet_requires_https_evidence_and_note():
    raw = '[{"address":"' + ADDR_A + '","label":"exchange","verification_status":"verified","evidence_url":"http://example.com/proof","evidence_note":"operator review"}]'
    with pytest.raises(ValueError, match="HTTPS evidence_url"):
        load_wallet_registry(raw, 1)


def test_registry_normalizes_addresses_and_preserves_provenance():
    raw = '[{"address":"' + ADDR_A.upper().replace("0X", "0x") + '","label":"smart_money","entity_name":"Example Research Wallet","verification_status":"verified","evidence_url":"https://example.org/report","evidence_note":"Public disclosure lists this address","last_reviewed_at":"2026-11-10"}]'
    result = load_wallet_registry(raw, 1)
    assert result["verified_count"] == 1
    row = annotate_wallet_addresses([ADDR_A], result)[0]
    assert row["label"] == "smart_money"
    assert row["verification_status"] == "verified"
    assert row["evidence_url"] == "https://example.org/report"


def test_registry_rejects_duplicate_addresses():
    raw = '[{"address":"' + ADDR_A + '"},{"address":"' + ADDR_A.upper().replace("0X", "0x") + '"}]'
    with pytest.raises(ValueError, match="Duplicate"):
        load_wallet_registry(raw, 1)
