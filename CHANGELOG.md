# Changelog

Versions are tagged per production. Newest first.

## Unreleased (since `padua-2026-final`)
- Warning in the chat when recording was interrupted in the background.
- UX event logging for later analysis of group interaction.
- Transcript bubble in the chat shows the full transcript, not only the first part.
- VAD pre-roll buffer measured and rejected (no production code change).

## padua-2026-final — 2026-11-08
Workshop version for Padua. Dortmund behaviour frozen since 2026-10-04.
- Silent discussion recording with watchdog, buffering and network-failure test.
- Hanging interview mode ends automatically; orphan banner.
- Phase summaries per phase (decisions only, no raw dumps).
- Play model: every fact stored in exactly one place.
- Quote selection fixed against a gold corpus; recogniser baseline and A/B measurements.
- Phase 3–7 hardened for live use (simulation, prompt checks, review rounds).
- VAD cuts at natural pauses instead of a hard 90 s cap.
- Web chat: autogrowing input, workbench status panel with new-item markers.

## dortmund-2026-final — 2026-09-06
First workshop version (Dortmund).
- Interview as a unit, seven phases, form and frame, scenes generated from structure.
- Mechanical interview mode instead of a permanent threshold.
- Telegram wrapper with normalisation; long messages split instead of HTTP 400.
- Soft delete commands; browser end-to-end run with Playwright.
