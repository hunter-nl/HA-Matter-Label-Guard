"""Matter-node discovery helpers shared by runtime and configuration flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LABELS, SUBENTRY_TYPE_NODE


@dataclass(frozen=True)
class MatterNodeInfo:
    """The current state needed to configure a Matter node label."""

    identifier: str
    label: str
    available: bool


def async_get_matter_clients(hass: HomeAssistant) -> list[Any]:
    """Return clients exposed by loaded Home Assistant Matter entries."""
    clients: list[Any] = []
    for entry in hass.config_entries.async_entries("matter"):
        runtime_data = getattr(entry, "runtime_data", None)
        adapter = getattr(runtime_data, "adapter", None)
        client = getattr(adapter, "matter_client", None)
        if client is not None:
            clients.append(client)
    return clients


def matter_client_available(hass: HomeAssistant) -> bool:
    """Return whether at least one loaded Matter client can be queried."""
    return bool(async_get_matter_clients(hass))


def discovered_nodes(hass: HomeAssistant, fabric_index: int) -> dict[str, MatterNodeInfo]:
    """Return nodes currently retained by the Matter server.

    Matter Server exposes node IDs as integers. The configured identifiers retain
    the integration's established ``@fabric:node`` representation.
    """
    nodes: dict[str, MatterNodeInfo] = {}
    for client in async_get_matter_clients(hass):
        for node in client.get_nodes():
            identifier = f"@{fabric_index:x}:{node.node_id:x}"
            nodes[identifier] = MatterNodeInfo(
                identifier=identifier,
                label=node.name or "",
                available=bool(node.available),
            )
    return nodes


def fabric_index(entry: ConfigEntry) -> int:
    """Use the configured fabric index, defaulting to Matter Server's first one."""
    identifiers = [
        subentry.unique_id
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_NODE and subentry.unique_id
    ]
    identifiers.extend((entry.options.get(CONF_LABELS) or entry.data.get(CONF_LABELS) or {}).keys())
    for identifier in identifiers:
        try:
            return int(identifier.removeprefix("@").split(":", maxsplit=1)[0], 16)
        except AttributeError, ValueError:
            continue
    return 1


def subentry_title(identifier: str, label: str, *, guarded: bool, deleted: bool) -> str:
    """Return the user-visible state and label for a node subentry."""
    state = "Deleted" if deleted else "Guarded" if guarded else "Not guarded"
    return f"{state}: {label or identifier} ({identifier})"
