import logging
import datetime
from src.anki_client import AnkiClient
from apyanki.anki import Anki
from src.config import config

logging.basicConfig(level=logging.INFO)

def debug_counts():
    anki = AnkiClient()
    with Anki(base_path=anki.base_path, profile="同期用") as a:
        for deck_name in config.DECKS_TO_TRACK:
            print(f"\nDeck: {deck_name}")
            
            # Try simple deck search
            all_cards = a.col.find_cards(f'deck:"{deck_name}"')
            print(f"  All cards in deck: {len(all_cards)}")
            
            # Try without is:review
            mature_no_review = a.col.find_cards(f'deck:"{deck_name}" -is:suspended prop:ivl>=21')
            young_no_review = a.col.find_cards(f'deck:"{deck_name}" -is:suspended prop:ivl>=1 prop:ivl<21')
            print(f"  Mature (no is:review): {len(mature_no_review)}")
            print(f"  Young (no is:review): {len(young_no_review)}")
            
            # Try with is:review
            mature_with_review = a.col.find_cards(f'deck:"{deck_name}" is:review -is:suspended prop:ivl>=21')
            young_with_review = a.col.find_cards(f'deck:"{deck_name}" is:review -is:suspended prop:ivl<21')
            print(f"  Mature (with is:review): {len(mature_with_review)}")
            print(f"  Young (with is:review): {len(young_with_review)}")

            # Try SQL to be absolutely sure
            query = """
                SELECT count(*) FROM cards 
                WHERE did IN (SELECT id FROM decks WHERE name = ? OR name LIKE ?)
                AND queue = 2 AND ivl >= 21 AND queue != -1
            """
            sql_mature = a.col.db.scalar(query, deck_name, f"{deck_name}::%")
            print(f"  SQL Mature (queue=2, ivl>=21): {sql_mature}")

if __name__ == "__main__":
    debug_counts()
