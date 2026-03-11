# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0-alpha.1] - 2026-03-11
### Added
- Initial orchestrator API scaffold (FastAPI + WebSocket live updates)
- Device registry with support for up to 25 devices
- Global visual state model (`grid_profile`, `preset`, `blanked_cells`, `revision`)
- Command dispatch endpoints for broadcast and per-device control
- Heartbeat and online/offline status tracking
- Web dashboard with:
  - config page
  - live status page
  - command console page
- Persistent local state storage (`data/state.json`)

