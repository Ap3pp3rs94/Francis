from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .capability_marketplace import CapabilityListing, CapabilityMarketplace

__all__ = ["capability_listings_from_plugin_catalog", "marketplace_from_plugin_catalog"]


def capability_listings_from_plugin_catalog(catalog: Mapping[str, Any]) -> list[CapabilityListing]:
    plugins = catalog.get("plugins")
    if not isinstance(plugins, list):
        return []

    listings: list[CapabilityListing] = []
    for item in plugins:
        if not isinstance(item, Mapping):
            continue
        listing = _listing_from_plugin(item)
        if listing is not None:
            listings.append(listing)
    return sorted(listings, key=lambda item: (item.capability, item.version, item.source))


def marketplace_from_plugin_catalog(catalog: Mapping[str, Any]) -> CapabilityMarketplace:
    marketplace = CapabilityMarketplace()
    for listing in capability_listings_from_plugin_catalog(catalog):
        marketplace.add_listing(listing)
    return marketplace


def _listing_from_plugin(plugin: Mapping[str, Any]) -> CapabilityListing | None:
    plugin_id = _text(plugin.get("plugin_id") or plugin.get("id"))
    if not plugin_id:
        return None

    metadata = _mapping(plugin.get("metadata") or plugin.get("meta"))
    quality = _quality_refs(metadata)
    return CapabilityListing(
        capability=plugin_id,
        price=0.0,
        version=_text(plugin.get("version"), fallback="0.1.0"),
        status=_status_from_metadata(metadata),
        risk_tier=_risk_from_plugin(plugin, metadata),
        source=_text(plugin.get("origin") or plugin.get("source_kind") or metadata.get("source"), fallback="unknown"),
        proposal_id=_text(metadata.get("proposal_id") or metadata.get("forge_proposal_id")),
        promotion_receipt_id=_text(metadata.get("promotion_receipt_id")),
        tests=quality["tests"],
        docs=quality["docs"],
        metadata=_catalog_metadata(plugin, metadata),
    )


def _catalog_metadata(plugin: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (
        "proposal_path",
        "promotion_receipt_path",
        "registry_snapshot_path",
        "validation_path",
        "validation_receipt_id",
        "validation_receipt_path",
        "known_limits",
        "proposal_evidence",
        "pack_id",
        "pack_version",
        "pack_name",
        "capability_pack_id",
        "capability_pack_version",
        "capability_pack_name",
        "promotion_rules",
        "promotion_rule_ids",
        "pack_governance",
        "capability_pack_governance",
        "pack_metadata_source",
        "pack_metadata_receipt_id",
        "pack_metadata_receipt_path",
        "pack_migration_reason",
    ):
        value = metadata.get(key)
        if value:
            out[key] = value

    if not (out.get("pack_id") or out.get("capability_pack_id")):
        out.update(_legacy_generated_pack_metadata(plugin, metadata))

    name = _text(plugin.get("name"))
    if name:
        out["plugin_name"] = name

    capabilities = plugin.get("capabilities")
    if isinstance(capabilities, list) and capabilities:
        out["capabilities"] = [str(item).strip() for item in capabilities if str(item).strip()]
    return out


def _quality_refs(metadata: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    quality = _mapping(metadata.get("quality"))
    tests = _str_tuple(metadata.get("tests") or metadata.get("test_refs") or quality.get("tests"))
    docs = _str_tuple(metadata.get("docs") or metadata.get("documentation") or quality.get("docs"))
    return {"tests": tests, "docs": docs}


def _risk_from_plugin(plugin: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    return _label(metadata.get("risk_tier") or plugin.get("risk_class") or plugin.get("risk_tier"), fallback="normal")


def _status_from_metadata(metadata: Mapping[str, Any]) -> str:
    return _label(metadata.get("promotion_status") or metadata.get("status"))


def _legacy_generated_pack_metadata(plugin: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    source = _label(plugin.get("origin") or plugin.get("source_kind") or metadata.get("source"))
    tags = _str_tuple(plugin.get("tags"))
    generated_dir = _text(plugin.get("generated_dir"))
    if source != "generated" and "generated" not in tags and not generated_dir:
        return {}

    plugin_id = _text(plugin.get("plugin_id") or plugin.get("id"))
    family = _legacy_generated_family(plugin_id)
    title = " ".join(part.capitalize() for part in family.split("_") if part) or "Unknown"
    return {
        "pack_id": f"legacy.generated.{family}",
        "pack_version": "0.0.0-migration",
        "pack_name": f"Legacy Generated {title} Pack",
        "pack_metadata_source": "legacy_generated_projection",
        "pack_migration_reason": "legacy_generated_artifact_missing_explicit_stage17_pack_metadata",
    }


def _legacy_generated_family(plugin_id: str) -> str:
    text = plugin_id.strip().lower()
    while text and text[0].isdigit():
        text = text[1:]
    text = text.lstrip("._-")

    normalized = "".join(ch if ch.isalnum() else "_" for ch in text)
    parts = [part for part in normalized.split("_") if part]
    family = "_".join(parts)
    return family[:80] or "unknown"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _label(value: Any, *, fallback: str = "unknown") -> str:
    return _text(value, fallback=fallback).lower()


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                parts.append(text)
        return tuple(parts)
    text = str(value).strip()
    return (text,) if text else ()
