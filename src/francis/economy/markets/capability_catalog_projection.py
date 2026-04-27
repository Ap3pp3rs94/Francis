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
        source=_text(plugin.get("origin") or metadata.get("source"), fallback="unknown"),
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
    ):
        value = metadata.get(key)
        if value:
            out[key] = value

    name = _text(plugin.get("name"))
    if name:
        out["plugin_name"] = name

    capabilities = plugin.get("capabilities")
    if isinstance(capabilities, list) and capabilities:
        out["capabilities"] = [str(item).strip() for item in capabilities if str(item).strip()]
    return out


def _quality_refs(metadata: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    tests = _str_tuple(metadata.get("tests") or metadata.get("test_refs"))
    docs = _str_tuple(metadata.get("docs") or metadata.get("documentation"))
    return {"tests": tests, "docs": docs}


def _risk_from_plugin(plugin: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    return _label(metadata.get("risk_tier") or plugin.get("risk_class") or plugin.get("risk_tier"), fallback="normal")


def _status_from_metadata(metadata: Mapping[str, Any]) -> str:
    return _label(metadata.get("promotion_status") or metadata.get("status"))


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
