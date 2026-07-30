"""Configuration flow for Matter Label Guard."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, ConfigSubentryFlow, SubentryFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector

from .const import (
    CONF_DELETED,
    CONF_GUARDED,
    CONF_IDENTIFIER,
    CONF_INTERVAL_MINUTES,
    CONF_LABEL,
    DEFAULT_INTERVAL_MINUTES,
    DOMAIN,
    SUBENTRY_TYPE_NODE,
)
from .nodes import discovered_nodes, fabric_index, matter_client_available, subentry_title


def _interval_schema(value: int) -> vol.Schema:
    """Return the simple setup/settings form."""
    return vol.Schema(
        {
            vol.Required(CONF_INTERVAL_MINUTES, default=value): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        }
    )


class MatterLabelGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Matter Label Guard."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the entry with the supplied check interval."""
        if user_input is not None:
            return self.async_create_entry(
                title="Matter Label Guard",
                data=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=_interval_schema(DEFAULT_INTERVAL_MINUTES))

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MatterLabelGuardOptionsFlow:
        """Return the editable settings flow."""
        return MatterLabelGuardOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Expose one editable subentry for each Matter node."""
        return {SUBENTRY_TYPE_NODE: NodeLabelSubentryFlow}


class NodeLabelSubentryFlow(ConfigSubentryFlow):
    """Configure whether a discovered Matter node label is guarded."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Choose a currently discovered node."""
        entry = self._get_entry()
        nodes = discovered_nodes(self.hass, fabric_index(entry))
        configured = {subentry.unique_id for subentry in entry.subentries.values()}
        choices = {
            identifier: f"{identifier} — {node.label or 'No label'}"
            for identifier, node in nodes.items()
            if identifier not in configured
        }
        if not choices:
            return self.async_abort(reason="no_nodes")
        if user_input is not None:
            self._identifier = user_input[CONF_IDENTIFIER]
            return await self.async_step_configure()
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_IDENTIFIER): vol.In(choices)})
        )

    async def async_step_configure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Set the proposed current label and guarding state."""
        entry = self._get_entry()
        node = discovered_nodes(self.hass, fabric_index(entry)).get(self._identifier)
        if node is None:
            return self.async_abort(reason="node_not_found")
        if user_input is not None:
            label = user_input[CONF_LABEL].strip()
            return self.async_create_entry(
                title=subentry_title(self._identifier, label, guarded=user_input[CONF_GUARDED], deleted=False),
                unique_id=self._identifier,
                data={
                    CONF_IDENTIFIER: self._identifier,
                    CONF_LABEL: label,
                    CONF_GUARDED: user_input[CONF_GUARDED],
                    CONF_DELETED: False,
                },
            )
        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LABEL, default=node.label): TextSelector(),
                    vol.Required(CONF_GUARDED, default=False): bool,
                }
            ),
            description_placeholders={
                "current_label": node.label,
                "status": "online" if node.available else "offline",
            },
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Show label settings and the refresh action for a node subentry."""
        return self.async_show_menu(step_id="reconfigure", menu_options=["settings", "refresh"])

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Update an existing node-label subentry."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        identifier = subentry.data[CONF_IDENTIFIER]
        node = discovered_nodes(self.hass, fabric_index(entry)).get(identifier)
        if user_input is not None:
            label = user_input[CONF_LABEL].strip()
            return self.async_update_reload_and_abort(
                entry,
                subentry,
                title=subentry_title(
                    identifier,
                    label,
                    guarded=user_input[CONF_GUARDED] and node is not None,
                    deleted=node is None,
                ),
                data={
                    CONF_IDENTIFIER: identifier,
                    CONF_LABEL: label,
                    CONF_GUARDED: user_input[CONF_GUARDED] and node is not None,
                    CONF_DELETED: node is None,
                },
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LABEL, default=subentry.data[CONF_LABEL]): TextSelector(),
                    vol.Required(CONF_GUARDED, default=subentry.data[CONF_GUARDED] and node is not None): bool,
                }
            ),
            description_placeholders={
                "current_label": node.label if node else "",
                "status": "online" if node and node.available else "deleted" if node is None else "offline",
            },
        )

    async def async_step_refresh(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Refresh only this node's retained/deleted and online/offline state."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        identifier = subentry.data[CONF_IDENTIFIER]
        if not matter_client_available(self.hass):
            return self.async_abort(reason="matter_unavailable")

        node = discovered_nodes(self.hass, fabric_index(entry)).get(identifier)
        data = {
            **subentry.data,
            CONF_DELETED: node is None,
            CONF_GUARDED: bool(subentry.data.get(CONF_GUARDED)) and node is not None,
        }
        self.hass.config_entries.async_update_subentry(
            entry=entry,
            subentry=subentry,
            title=subentry_title(
                identifier,
                str(data[CONF_LABEL]),
                guarded=bool(data[CONF_GUARDED]),
                deleted=bool(data[CONF_DELETED]),
            ),
            data=data,
        )
        return self.async_abort(
            reason="refresh_successful",
            description_placeholders={
                "status": "deleted" if node is None else "online" if node.available else "offline"
            },
        )


class MatterLabelGuardOptionsFlow(config_entries.OptionsFlowWithReload):
    """Provide the parent check-interval and node-status summary."""

    def _settings(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the parent settings summary."""
        entry = self.config_entry
        nodes = discovered_nodes(self.hass, fabric_index(entry)) if matter_client_available(self.hass) else {}
        subentries = [
            subentry for subentry in entry.subentries.values() if subentry.subentry_type == SUBENTRY_TYPE_NODE
        ]
        guarded = sum(
            bool(subentry.data.get(CONF_GUARDED)) and not subentry.data.get(CONF_DELETED) for subentry in subentries
        )
        deleted = sum(bool(subentry.data.get(CONF_DELETED)) for subentry in subentries)
        configured = {subentry.unique_id for subentry in subentries}
        offline = sum(not node.available for identifier, node in nodes.items() if identifier in configured)
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings"],
            description_placeholders={
                "nodes": str(len(subentries)),
                "guarded": str(guarded),
                "offline": str(offline),
                "deleted": str(deleted),
            },
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the check interval."""
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._settings(), **user_input})
        return self.async_show_form(
            step_id="settings",
            data_schema=_interval_schema(self._settings()[CONF_INTERVAL_MINUTES]),
        )
