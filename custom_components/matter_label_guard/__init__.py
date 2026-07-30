#!/usr/bin/env python3

"""Restore missing Matter node labels."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_INTERVAL_MINUTES, CONF_LABELS, NODE_LABEL_PATH
from .labels import DEFAULT_LABELS

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up periodic checking for a configured label map."""
    guard = MatterLabelGuard(hass, entry)
    # Do not block config-entry setup on sleepy/offline Matter nodes.  Matter
    # reads can wait for a device to wake, which would otherwise leave this
    # integration in the "Initializing" state.
    entry.runtime_data = guard
    hass.async_create_task(guard.async_restore_missing_labels())
    interval = timedelta(minutes=guard.interval_minutes)
    entry.async_on_unload(async_track_time_interval(hass, guard.async_restore_missing_labels, interval))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return True


class MatterLabelGuard:
    """Check the Matter server and restore labels that are empty."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        settings: dict[str, Any] = {**entry.data, **entry.options}
        self.interval_minutes = int(settings[CONF_INTERVAL_MINUTES])
        self.labels: dict[str, str] = settings.get(CONF_LABELS, DEFAULT_LABELS)
        self._restore_lock = asyncio.Lock()

    async def async_restore_missing_labels(self, *_: Any) -> None:
        """Read NodeLabel from each mapped node and fill only empty labels."""
        if self._restore_lock.locked():
            return
        async with self._restore_lock:
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
                    for identifier, label in self.labels.items()
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

    def _matter_clients(self):
        """Yield Matter clients owned by currently loaded Matter entries."""
        for entry in self.hass.config_entries.async_entries("matter"):
            runtime_data = getattr(entry, "runtime_data", None)
            adapter = getattr(runtime_data, "adapter", None)
            client = getattr(adapter, "matter_client", None)
            if client is not None:
                yield client

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
