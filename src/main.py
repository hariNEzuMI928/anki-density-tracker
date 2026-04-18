import logging
import datetime
from .anki_client import AnkiClient
from .sheets_client import SheetsClient
from .slack_client import SlackClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run():
    anki = AnkiClient()
    sheets = SheetsClient()
    slack = SlackClient()

    if anki.is_running():
        logger.warning("Anki is running. Skipping to avoid DB lock.")
        return

    try:
        anki.sync()
    except Exception as e:
        logger.error(f"Sync failed, continuing with local data: {e}")

    now = datetime.datetime.now()
    today_start = datetime.datetime(now.year, now.month, now.day)
    
    stats, new_counts = anki.get_stats(today_start)
    
    if stats:
        sheets.update_stats(stats)
    
    slack.notify_progress(new_counts)
    
    logger.info("Process completed.")

if __name__ == "__main__":
    run()
