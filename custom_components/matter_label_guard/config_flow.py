"""Configuration flow for Matter Label Guard."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import CONF_INTERVAL_MINUTES, CONF_LABELS, DEFAULT_INTERVAL_MINUTES, DOMAIN
from .labels import DEFAULT_LABELS

CONF_IDENTIFIER = "identifier"
CONF_LABEL = "label"


def _interval_schema(value: int) -> vol.Schema:
    """Return the simple setup/settings form."""
    return vol.Schema(
        {
            vol.Required(CONF_INTERVAL_MINUTES, default=value): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        }
    )


class MatterLabelGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Matter Label Guard."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the entry with the supplied labels."""
        if user_input is not None:
            return self.async_create_entry(
                title="Matter Label Guard",
                data={**user_input, CONF_LABELS: dict(DEFAULT_LABELS)},
            )
        return self.async_show_form(step_id="user", data_schema=_interval_schema(DEFAULT_INTERVAL_MINUTES))

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MatterLabelGuardOptionsFlow:
        """Return the editable settings flow."""
        return MatterLabelGuardOptionsFlow()


class MatterLabelGuardOptionsFlow(config_entries.OptionsFlowWithReload):
    """Provide label management forms."""

    def _settings(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    def _labels(self) -> dict[str, str]:
        return dict(self._settings().get(CONF_LABELS, DEFAULT_LABELS))

    def _labels_summary(self) -> str:
        """Return the configured labels for the options-menu description."""
        return "\n".join(f"{identifier} → {label}" for identifier, label in sorted(self._labels().items()))

    @callback
    def _identifier_selector(self) -> Any:
        return SelectSelector(SelectSelectorConfig(options=sorted(self._labels())))

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the settings and label-management menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "settings",
                "add_label",
                "edit_label",
                "remove_label",
                "reset_labels",
            ],
            description_placeholders={"labels": self._labels_summary()},
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the check interval."""
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._settings(), **user_input})
        return self.async_show_form(
            step_id="settings",
            data_schema=_interval_schema(self._settings()[CONF_INTERVAL_MINUTES]),
        )

    async def async_step_add_label(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a node label."""
        errors: dict[str, str] = {}
        if user_input is not None:
            identifier = user_input[CONF_IDENTIFIER].strip().lower()
            if not _valid_identifier(identifier):
                errors[CONF_IDENTIFIER] = "invalid_identifier"
            elif identifier in self._labels():
                errors[CONF_IDENTIFIER] = "identifier_exists"
            elif not user_input[CONF_LABEL].strip():
                errors[CONF_LABEL] = "invalid_label"
            else:
                labels = self._labels()
                labels[identifier] = user_input[CONF_LABEL].strip()
                return self.async_create_entry(title="", data={**self._settings(), CONF_LABELS: labels})
        return self.async_show_form(
            step_id="add_label",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IDENTIFIER): TextSelector(),
                    vol.Required(CONF_LABEL): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_label(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the node whose label should change."""
        if user_input is not None:
            self._selected_identifier = user_input[CONF_IDENTIFIER]
            return await self.async_step_edit_value()
        return self.async_show_form(
            step_id="edit_label",
            data_schema=vol.Schema({vol.Required(CONF_IDENTIFIER): self._identifier_selector()}),
        )

    async def async_step_edit_value(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the selected node's label."""
        identifier = self._selected_identifier
        if user_input is not None:
            if user_input[CONF_LABEL].strip():
                labels = self._labels()
                labels[identifier] = user_input[CONF_LABEL].strip()
                return self.async_create_entry(title="", data={**self._settings(), CONF_LABELS: labels})
            return self.async_show_form(
                step_id="edit_value",
                data_schema=vol.Schema({vol.Required(CONF_LABEL, default=self._labels()[identifier]): TextSelector()}),
                errors={CONF_LABEL: "invalid_label"},
                description_placeholders={"identifier": identifier},
            )
        return self.async_show_form(
            step_id="edit_value",
            data_schema=vol.Schema({vol.Required(CONF_LABEL, default=self._labels()[identifier]): TextSelector()}),
            description_placeholders={"identifier": identifier},
        )

    async def async_step_remove_label(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Remove one node label."""
        if user_input is not None:
            labels = self._labels()
            labels.pop(user_input[CONF_IDENTIFIER], None)
            return self.async_create_entry(title="", data={**self._settings(), CONF_LABELS: labels})
        return self.async_show_form(
            step_id="remove_label",
            data_schema=vol.Schema({vol.Required(CONF_IDENTIFIER): self._identifier_selector()}),
        )

    async def async_step_reset_labels(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer a confirmation before restoring the supplied list."""
        if user_input is not None:
            return self.async_create_entry(title="", data={**self._settings(), CONF_LABELS: dict(DEFAULT_LABELS)})
        return self.async_show_form(step_id="reset_labels")


def _valid_identifier(identifier: str) -> bool:
    """Validate the Matter Server @fabric:node hexadecimal notation."""
    try:
        fabric, node = identifier.removeprefix("@").split(":", maxsplit=1)
        return identifier.startswith("@") and bool(fabric) and int(fabric, 16) >= 0 and int(node, 16) >= 0
    except ValueError:
        return False
