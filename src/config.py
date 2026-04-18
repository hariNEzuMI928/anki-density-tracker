import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    DECKS_TO_TRACK = ["1_Vocabulary", "2_EnglishComposition", "3_FluencyTest"]
    TARGET_DECKS = ["2_EnglishComposition", "3_FluencyTest"]
    
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
    SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
    
    # Paths
    PROJECT_ROOT = Path(__file__).parent.parent
    CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
    ANKI_BASE = Path(os.path.expanduser("~/Library/Application Support/Anki2"))
    
    # Scheduler
    FORCE_NOTIFY = os.environ.get("FORCE_NOTIFY") == "True"

config = Config()
