# Technical Design

## Boundaries

- Vue state remains shared through the existing module-level `config` reactive object. `useConfigState.js` owns the selected configuration name, last-saved snapshot, new-config dialog handshake, and localStorage restoration.
- FastAPI keeps the existing configuration CRUD contract. Upload references are optional fields in `ParameterDocument`; existing JSON documents remain valid.
- `UploadStore` persists only upload metadata and file paths. Configuration files remain the source of truth for whether an upload is still referenced.

## Upload persistence

`UploadStore` writes `uploads/_index.json` atomically. Each record stores the upload ID, server file path, original filename, byte size, and ISO timestamp. On startup it restores only records whose files still exist. Cleanup scans the configured JSON directory and skips referenced upload IDs before applying the existing TTL.

The frontend saves `old_file_upload_id` and `new_file_upload_id` alongside the display filenames. Loading a saved configuration restores both fields. Job submission still blanks the path fields and sends only upload IDs, preserving the existing backend validation that rejects path/upload combinations.

## UI flow

`NewConfigDialog` is rendered once by `App.vue`, while sidebar and start/save actions open it through `useConfigState`. Template import applies the fetched template while preserving current file selections; cancelling restores the pre-dialog config snapshot. Save and start share the same save path, so auto-save cannot diverge from manual save.

Progress actions are owned by `ProgressPanel`: the start/stop control is status-driven, report download is available only after completion, and log download is available once logs exist. A completed job disables start; failed and cancelled jobs may retry.

## Compatibility

- Old config files without upload IDs load with cleared upload references and require a new upload.
- Built-in templates remain served by the existing config GET endpoint and are filtered only from the visible user list.
- No frontend test runner is introduced; production Vite build and browser smoke checks cover the UI surface for this iteration.
