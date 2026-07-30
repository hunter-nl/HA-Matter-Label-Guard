"""Constants for Matter Label Guard."""

DOMAIN = "matter_label_guard"
CONF_INTERVAL_MINUTES = "interval_minutes"
CONF_LABELS = "labels"
CONF_GUARDED = "guarded"
CONF_IDENTIFIER = "identifier"
CONF_LABEL = "label"
CONF_DELETED = "deleted"
DEFAULT_INTERVAL_MINUTES = 30
SUBENTRY_TYPE_NODE = "node_label"

# Basic Information cluster (0x0028) / NodeLabel attribute (0x0005), endpoint 0.
NODE_LABEL_PATH = "0/40/5"
