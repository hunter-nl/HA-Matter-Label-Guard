#!/usr/bin/env python3

"""Restore missing Matter node labels."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_DELETED,
    CONF_GUARDED,
    CONF_IDENTIFIER,
    CONF_INTERVAL_MINUTES,
    CONF_LABEL,
    CONF_LABELS,
    NODE_LABEL_PATH,
    SUBENTRY_TYPE_NODE,
)
from .labels import DEFAULT_LABELS
from .nodes import async_get_matter_clients, discovered_nodes, fabric_index, matter_client_available, subentry_title

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up periodic checking for a configured label map."""
    guard = MatterLabelGuard(hass, entry)
    # Do not block config-entry setup on sleepy/offline Matter nodes.  Matter
    # reads can wait for a device to wake, which would otherwise leave this
    # integration in the "Initializing" state.
    entry.runtime_data = guard
    await guard.async_sync_nodes()
    hass.async_create_task(guard.async_restore_missing_labels())
    interval = timedelta(minutes=guard.interval_minutes)
    entry.async_on_unload(async_track_time_interval(hass, guard.async_restore_missing_labels, interval))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Move legacy label mappings to individually managed node subentries."""
    if entry.version >= 2:
        return True
    settings = {**entry.data, **entry.options}
    labels = settings.get(CONF_LABELS, DEFAULT_LABELS)
    for identifier, label in labels.items():
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                subentry_type=SUBENTRY_TYPE_NODE,
                title=subentry_title(identifier, label, guarded=True, deleted=False),
                unique_id=identifier,
                data=MappingProxyType(
                    {CONF_IDENTIFIER: identifier, CONF_LABEL: label, CONF_GUARDED: True, CONF_DELETED: False}
                ),
            ),
        )
    hass.config_entries.async_update_entry(
        entry,
        data={key: value for key, value in entry.data.items() if key != CONF_LABELS},
        options={key: value for key, value in entry.options.items() if key != CONF_LABELS},
        version=2,
    )
    return True


class MatterLabelGuard:
    """Check the Matter server and restore labels that are empty."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        settings: dict[str, Any] = {**entry.data, **entry.options}
        self.interval_minutes = int(settings[CONF_INTERVAL_MINUTES])
        self.entry = entry
        self._restore_lock = asyncio.Lock()

    async def async_restore_missing_labels(self, *_: Any) -> None:
        """Read NodeLabel from each mapped node and fill only empty labels."""
        if self._restore_lock.locked():
            return
        async with self._restore_lock:
            await self.async_sync_nodes()
            clients = list(self._matter_clients())
            if not clients:
                LOGGER.warning("No loaded Matter integration was found; will try again later")
                return

            # Limit concurrent Matter reads so a large group of devices does
            # not flood the controller, while one offline node cannot stall a
            # complete scan.
            semaphore = asyncio.Semaphore(3)
            await asyncio.gather(
                *(
                    self._check_client_label(client, identifier, label, semaphore)
                    for client in clients
                    for identifier, label in self._guarded_labels().items()
                )
            )

    async def _check_client_label(self, client: Any, identifier: str, label: str, semaphore: asyncio.Semaphore) -> None:
        """Restore one label, limiting device wake-up/read time."""
        if self._node_id(identifier) is None:
            LOGGER.warning("Ignoring invalid Matter node identifier: %s", identifier)
            return
        try:
            async with semaphore, asyncio.timeout(15):
                values = await client.read_attribute(identifier, NODE_LABEL_PATH)
                current_label = values.get(NODE_LABEL_PATH)
                if isinstance(current_label, str) and current_label.strip():
                    return
                await client.write_attribute(identifier, NODE_LABEL_PATH, label)
                LOGGER.info("Restored Matter node label %r on %s", label, identifier)
        except Exception as err:  # A sleepy or temporarily-offline node is retried later.
            LOGGER.debug("Could not check Matter node %s: %s", identifier, err)

    async def async_sync_nodes(self) -> None:
        """Add discovered nodes and mark only truly removed nodes as deleted."""
        if not matter_client_available(self.hass):
            LOGGER.debug("Matter integration is not loaded; skipping node synchronization")
            return
        nodes = discovered_nodes(self.hass, fabric_index(self.entry))
        existing = {
            sub.unique_id: sub for sub in self.entry.subentries.values() if sub.subentry_type == SUBENTRY_TYPE_NODE
        }
        for identifier, node in nodes.items():
            if identifier not in existing:
                self.hass.config_entries.async_add_subentry(
                    self.entry,
                    ConfigSubentry(
                        subentry_type=SUBENTRY_TYPE_NODE,
                        title=subentry_title(identifier, node.label, guarded=False, deleted=False),
                        unique_id=identifier,
                        data=MappingProxyType(
                            {
                                CONF_IDENTIFIER: identifier,
                                CONF_LABEL: node.label,
                                CONF_GUARDED: False,
                                CONF_DELETED: False,
                            }
                        ),
                    ),
                )
            elif existing[identifier].data.get(CONF_DELETED):
                sub = existing[identifier]
                data = {**sub.data, CONF_DELETED: False}
                self.hass.config_entries.async_update_subentry(
                    self.entry,
                    sub,
                    data=data,
                    title=subentry_title(
                        identifier, str(data[CONF_LABEL]), guarded=bool(data[CONF_GUARDED]), deleted=False
                    ),
                )
        for identifier, sub in existing.items():
            if identifier not in nodes and not sub.data.get(CONF_DELETED):
                data = {**sub.data, CONF_DELETED: True, CONF_GUARDED: False}
                self.hass.config_entries.async_update_subentry(
                    self.entry,
                    sub,
                    data=data,
                    title=subentry_title(str(identifier), str(data[CONF_LABEL]), guarded=False, deleted=True),
                )

    def _guarded_labels(self) -> dict[str, str]:
        """Return only extant nodes whose label protection is enabled."""
        subentries = [sub.data for sub in self.entry.subentries.values() if sub.subentry_type == SUBENTRY_TYPE_NODE]
        if subentries:
            return {
                data[CONF_IDENTIFIER]: data[CONF_LABEL]
                for data in subentries
                if data.get(CONF_GUARDED) and not data.get(CONF_DELETED)
            }
        return {**self.entry.data, **self.entry.options}.get(CONF_LABELS, DEFAULT_LABELS)

    def _matter_clients(self):
        """Yield Matter clients owned by currently loaded Matter entries."""
        yield from async_get_matter_clients(self.hass)

    @staticmethod
    def _node_id(identifier: str) -> tuple[int, int] | None:
        """Convert an identifier such as ``@1:2a`` to (fabric, node) tuple.

        Validates the Matter Server node identifier format:
         - Must start with ``@``
         - Must contain exactly one ``:`` separating fabric and node
         - Both fabric and node must be valid hexadecimal values
        """
        try:
            fabric_hex, node_hex = identifier.removeprefix("@").split(":", maxsplit=1)
            if not fabric_hex or not node_hex:
                return None
            return int(fabric_hex, 16), int(node_hex, 16)
        except AttributeError, ValueError:
            return None
