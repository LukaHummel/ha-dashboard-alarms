# HACS default repository submission

Submit `LukaHummel/ha-dashboard-alarms` as an **integration**, by adding that exact string in sorted order to the `integration` file in a new branch of a personal fork of [hacs/default](https://github.com/hacs/default). Enable maintainer edits on the PR. Do not request reviews.

The repository meets the integration layout requirements: one domain under `custom_components/`, all runtime files inside that directory, a complete manifest, a bundled 256x256 brand icon, and README rendering through `hacs.json`. It is public, has an Apache-2.0 license, description and topics, enables issues, and does not replace a core integration.

The integration ships local brand assets supported by Home Assistant 2026.3 and newer; this project requires 2026.10. Current [HACS brand validation](https://github.com/hacs/integration/blob/main/custom_components/hacs/validate/brands.py) accepts `brand/icon.png` before consulting the central brands repository. The default-list workflow uses this same HACS action, so a separate brands PR is not required for this layout.

The first published release was created after these successful validation jobs, with no ignored HACS checks:

- [Current published release: v0.1.1](https://github.com/LukaHummel/ha-dashboard-alarms/releases/tag/v0.1.1)
- [Successful HACS validation](https://github.com/LukaHummel/ha-dashboard-alarms/actions/runs/38082332355/job/114301638926)
- [Successful hassfest validation](https://github.com/LukaHummel/ha-dashboard-alarms/actions/runs/38082332355/job/114301638893)

The repository was absent from both the default integration list and removed list when checked on 2026-10-10. Before submitting, merge the Release Please setup and wait for its main validation to succeed. Use the latest published release and successful HACS/hassfest run links in the upstream PR template; refresh the links above if a newer release has been published. Recheck the lists before submitting. The submitter must be the repository owner or a major contributor; the owner here is `LukaHummel`.

Reference: [integration requirements](https://www.hacs.dev/docs/publish/integration/), [default-list submission requirements](https://www.hacs.dev/docs/publish/include/), and the [upstream PR checklist](https://github.com/hacs/default/blob/master/.github/PULL_REQUEST_TEMPLATE.md).
