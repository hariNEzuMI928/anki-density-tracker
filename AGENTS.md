# GEMINI.md - Anki Density Tracker

## Project Overview
Anki study density analysis and progress notification system. It tracks Anki learning data, visualizes 'density' in Google Sheets, and sends progress reports for monthly new card targets to Slack.

- **Tech Stack**: Python 3.12+, `apy` (Anki wrapper), `gspread` (Google Sheets), Slack Webhooks.
- **Architecture**:
    - `src/main.py`: Entry point. Orchestrates sync, data extraction, and notifications.
    - `src/anki_client.py`: Handles Anki DB access via `apy` and direct SQLite queries.
    - `src/sheets_client.py`: Manages Google Sheets updates for study logs and card maturity stats.
    - `src/slack_client.py`: Generates and sends progress reports with visual status bars.
- **Execution Environment**: macOS (optimized for local Anki setup), scheduled via `launchd`.

## Building and Running

### Prerequisites
- macOS (tested on Sequoia 15.5)
- `pyenv` and Python 3.12.0
- Anki Desktop installed with a profile named "同期用" (for sync).

### Setup
1. **Environment**:
    ```bash
    pyenv local 3.12.0
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
2. **Configuration**:
    - Copy `.env.example` to `.env` and fill in `SLACK_WEBHOOK_URL` and `SPREADSHEET_ID`.
    - Place Google Cloud service account credentials in `credentials.json` at the project root.

### Commands
- **Run Tracker**: `mise run run` (Note: Fails if Anki is running to avoid DB lock).
- **Manual Sync**: `.venv/bin/apy sync` (used internally by `AnkiClient`).
- **Development/Debug**: `python scratch/debug_counts.py` for testing specific counters.

## Development Conventions

### Coding Style
- **Type Hinting**: Use Python type hints for clarity (especially in `src/` clients).
- **Logging**: Use the standard `logging` module. `src/main.py` configures the root logger.
- **Configuration**: All settings should be centralized in `src/config.py`.

### Key Logics
- **Sync Safety**: `AnkiClient.is_running()` checks for the `Anki` process using `pgrep`. Always check this before DB operations.
- **Deck Tracking**: Target decks (`1_Vocabulary`, `2_EnglishComposition`, `3_FluencyTest`) are hardcoded in `src/config.py`.
- **Maturity Definition**: "Mature" cards are those with an interval >= 21 days.

### Testing
- No formal test suite (pytest) is currently present.
- Use `scratch/` directory for reproduction scripts and one-off tests.
- **Validation**: Before committing changes, run the tracker locally (with Anki closed) to ensure no regressions in Sheets/Slack output.

## Maintenance
- **Logs**: Standard output is captured by `launchd` in `logs/` (if configured in plist).
- **Scheduler**: Templates for `launchd` are in `launchd/com.user.anki-density-tracker.plist.template`.
