# Matter Label Guard

<img src="brand/logo.svg" alt="Matter Label Guard" style="max-width: 750px;">

[![Release][release-badge]][release-url]
[![Validate][validate-badge]][validate-url]
[![CI][ci-badge]][ci-url]
[![License][license-badge]][license-url]
[![Home-Assistant][ha-badge]][ha-url]
[![HACS Custom][hacs-badge]][hacs-url]

[release-badge]: https://img.shields.io/github/v/release/hunter-nl/HA-Matter-Label-Guard?include_prereleases&sort=semver&display_name=release&label=Release
[release-url]: https://github.com/hunter-nl/HA-Matter-Label-Guard/releases
[validate-badge]: https://img.shields.io/github/actions/workflow/status/hunter-nl/HA-Matter-Label-Guard/validate.yaml?label=Validate
[validate-url]: https://github.com/hunter-nl/HA-Matter-Label-Guard/actions/workflows/validate.yaml
[ci-badge]: https://img.shields.io/github/actions/workflow/status/hunter-nl/HA-Matter-Label-Guard/ci.yaml?label=CI
[ci-url]: https://github.com/hunter-nl/HA-Matter-Label-Guard/actions/workflows/ci.yaml
[license-badge]: https://img.shields.io/github/license/hunter-nl/HA-Matter-Label-Guard?color=blue
[license-url]: https://github.com/hunter-nl/HA-Matter-Label-Guard/blob/main/LICENSE
[ha-badge]: https://img.shields.io/badge/Home--Assistant-2026.7.0%2B-green?logo=homeassistant
[ha-url]: https://home-assistant.io
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistantcommunitystore&logoColor=white
[hacs-url]: https://www.hacs.xyz/docs/faq/custom_repositories/

This Home Assistant custom integration protects the Matter `NodeLabel` attribute.
Shortly after startup and at the configured interval (30 minutes by default), it
reads each mapped node's label and writes its configured label **only when the
current label is empty**. It never replaces a non-empty label. The initial scan
runs in the background, so offline or sleeping devices cannot hold up startup.

## What it does

- Restores the configured label only when a Matter device reports a blank or
  missing `NodeLabel`.
- Checks labels after Home Assistant starts and at an interval from 1 minute to
  24 hours.
- Retries unreachable or sleeping devices at the next scheduled check.
- Discovers Matter nodes automatically and manages each one as a native Home Assistant subentry.
- Lets you refresh the Matter node list on demand, including each node's online/offline status.

It is intentionally conservative: changing a label directly on a device or in
another Matter client is preserved as long as that label is not empty.

## Requirements

- Home Assistant 2026.7.0 or newer.
- The built-in Matter integration must already be configured and connected to
  Matter Server.
- The Matter device must be commissioned to that Matter Server.

## Install

### HACS (Recommended)

1. Open **HACS** → **⋮** → **Custom repositories**
2. Add repository: `hunter-nl/HA-Matter-Label-Guard`, category: **Integration**
3. Find **Matter Label Guard** and download it
4. Restart Home Assistant
5. Add **Matter Label Guard** in **Settings → Devices & services → Add
   integration**. Choose the check interval and submit it.

### Manual

1. Copy `custom_components/matter_label_guard` into your Home Assistant
   `/config/custom_components/` directory.
2. Restart Home Assistant
3. Add **Matter Label Guard** in **Settings → Devices & services → Add
   integration**. Choose the check interval and submit it.

The integration uses Home Assistant's existing Matter Server connection; it does
not need a Matter Server URL, token, or a second WebSocket client.

## Upgrade

### HACS

HACS checks this custom repository for published releases and shows an available
update in **Settings → Updates** (or as **Pending update** in HACS). Before
upgrading, create a Home Assistant backup and read the release notes. Install
the update (by redownload), then restart Home Assistant. Your existing integration
configuration and label mappings are retained.

### Manual

1. Create a Home Assistant backup.
2. Replace `/config/custom_components/matter_label_guard` with the
   `custom_components/matter_label_guard` directory from the desired release.
3. Restart Home Assistant.

## Configure node labels

After adding the integration, Matter Label Guard discovers the nodes retained by
Home Assistant's Matter Server and creates one **Matter node** subentry for
each. Open **Configure** on the parent integration and choose **Refresh Matter
node list** to update the list and each node's online/offline status immediately.
The Configure page shows when this list was last refreshed.

Open a node’s settings to see its current Matter label, choose the label to
restore, and enable **Guard this label**. An unguarded node is kept in the list
but is never changed.

Node titles start with the numeric Matter node ID and its Matter identifier, for
example `Node 014 (@1:e) Frontdoor`.
`🛡` means its label is guarded; `⚠` means the node is currently offline; and
`❌` means it has been deleted from Matter Server, which also disables guarding.
Opening a node's settings action shows its current Matter label and status, and
lets you edit the guarded label or enable and disable guarding.

The parent integration’s **Configure** screen shows the total number of node
entries and the guarded, offline, and deleted counts, plus the last refresh
time. It provides actions to refresh the node list and change the check
interval. Deleting a subentry stops Matter Label Guard from restoring that
node's label.

## Troubleshooting

- If a label is not restored, first confirm that the device is online and that
  its current label is empty. Non-empty labels are never overwritten.
- Confirm that the node identifier belongs to the Matter Server used by Home
  Assistant and is written as `@<fabric-id>:<node-id>` in hexadecimal.
- A device that is asleep or temporarily offline is retried at the next check;
  it does not prevent other devices from being checked.
- Enable debug logging for `custom_components.matter_label_guard` when filing a
  problem report. A sample logger configuration is in
  [`config/configuration.yaml`](config/configuration.yaml).

## Support

- [GitHub Issues](https://github.com/hunter-nl/HA-Matter-Label-Guard/issues)
- [Home Assistant Community](https://community.home-assistant.io/)

## Funding

If you find this project useful, consider supporting its development:

<a href="https://www.buymeacoffee.com/hunter.nl" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;"></a>
