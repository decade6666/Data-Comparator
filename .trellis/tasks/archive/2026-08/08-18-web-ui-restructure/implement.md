# Implementation Checklist

- [x] Create and start Trellis task; capture requirements and decisions in `prd.md`.
- [x] Add optional upload IDs to `ParameterDocument`.
- [x] Persist `UploadStore` records to `uploads/_index.json`, reload them, and skip config-referenced records during TTL cleanup.
- [x] Add upload-status API and tests for persistence, cleanup exemption, missing files, and config round-trip.
- [x] Add shared config-state composable with snapshot/revert, auto-save, new-config dialog handshake, and last-config restoration.
- [x] Add template-aware new configuration dialog and restructure the sidebar actions/list.
- [x] Move save/revert controls into the comparison-parameter panel.
- [x] Move start/report/log actions into the progress panel and remove the header action component.
- [x] Replace the merge-deleted-data checkbox with a labelled switch.
- [x] Put structure and color panels into a responsive side-by-side layout.
- [x] Expand the help dialog with the adapted five-section migration-era help text and GitHub URL.
- [x] Run backend tests, Vite production build, browser snapshot/screenshot smoke checks, and syntax/whitespace checks.
- [x] Review the final diff; report that ESLint cannot run because the repository has no ESLint configuration.
