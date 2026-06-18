# GEMINI.md - LoL Notifier Plugin for AstrBot

This document provides context and guidelines for developing and interacting with the `astrbot_plugin_lol_notifier` project.

## Project Overview

**LoL Notifier** is a plugin for [AstrBot](https://github.com/AstrBotDevs/AstrBot) that provides LoL esports notifications and on-demand query commands (e.g., schedules, results, BP, standings).

- **Primary Language:** Python (>= 3.10)
- **Key Libraries:** `aiohttp`, `Pillow`, `cairosvg`, `pydantic`.
- **Data Sources:**
    - To be integrated: public LCK/LPL schedule, result, BP, and standings sources.

## Architecture & Module Breakdown

The project follows a modular structure within the `src/astrbot_plugin_lol_notifier/` directory:

- `main.py`: Entry point for AstrBot. Registers the `LoLNotifierPlugin` class, handles command routing (`/lol ...`), and manages the lifecycle of the scheduler.
- `api.py`: Future LoL data fetcher boundary. Implements input validation and returns `Success`/`Failure` result types.
- `scheduler.py`: Background subscription skeleton that persists subscriber state and leaves room for future notification polling.
- `image_renderer.py`: Generates simple LoL graphics (PNGs) using Pillow.
- `formatter.py`: Logic for converting raw API data into human-friendly text messages.
- `models.py`: Pydantic data models for structured API responses and internal data representations.

## Key Files & Assets

- `assets/`: Existing assets can be reused or replaced when LoL-specific rendering is added.
- `metadata.yaml`: Plugin metadata for AstrBot (name, version, author, dependencies).
- `_conf_schema.json`: Configuration schema for AstrBot's Web UI.

## Building and Running

### Prerequisites
- Python 3.10+
- AstrBot environment.
- Dependencies: `pip install aiohttp cairosvg pillow pydantic`.

### Development & Testing
- **Local Testing:** You can run tests via `pytest`.
    ```bash
    pytest tests/
    ```
- **AstrBot Integration:** To run the plugin, place the entire directory in the AstrBot `data/plugins/` folder and enable it via the AstrBot dashboard.
- **Commands (Prefix: `/lol`):**
    - `schedule [lck|lpl] [regular|playoff] [season]`: Match schedule.
    - `result [lck|lpl] [regular|playoff] [round]`: Match results.
    - `bp [lck|lpl] [regular|playoff] [round]`: Single-game BP.
    - `detail [lck|lpl] [regular|playoff] [round]`: Match detail information.
    - `standings [lck|lpl] [regular|playoff] [season]`: Rankings / standings.
    - `subscribe`/`unsubscribe`: Manage auto-notifications for a session.

## Development Conventions

- **Result Pattern:** API calls in `api.py` return `Success(value=...)` or `Failure(error=...)`. Always handle both cases using `match` or `if`.
- **Image Rendering:** The plugin supports both text-only and image-enhanced modes. Use `_render_or_text` in `main.py` to handle the `enable_image_render` config flag gracefully.
- **Async First:** All network I/O and scheduling must be non-blocking. Use `aiohttp` and `asyncio`.
- **Data Persistence:** Subscriptions and notification state are stored in AstrBot's KV storage (`star.put_kv_data`). Do not use local files for session-specific state.
- **Scalability:** Image rendering is done at 2x resolution (`SCALE = 2`) for sharpness.

## TODOs & Future Improvements
- [ ] Implement more robust caching for API responses to reduce rate-limit risks.
- [ ] Add more circuit-specific graphics or driver photos if possible.
- [ ] Enhance error messaging for users when APIs are down or data is delayed.
