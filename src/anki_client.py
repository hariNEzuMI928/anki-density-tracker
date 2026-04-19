import os
import subprocess
import datetime
import logging
from typing import List, Dict, Tuple, Any
from apyanki.anki import Anki
from .config import config

logger = logging.getLogger(__name__)

class AnkiClient:
    def __init__(self):
        self.base_path = str(config.ANKI_BASE)

    def is_running(self) -> bool:
        try:
            output = subprocess.check_output(["pgrep", "-x", "Anki"], stderr=subprocess.STDOUT)
            return len(output) > 0
        except subprocess.CalledProcessError:
            return False

    def sync(self) -> None:
        logger.info("Syncing Anki...")
        try:
            apy_path = config.PROJECT_ROOT / ".venv" / "bin" / "apy"
            subprocess.run([str(apy_path), "-b", self.base_path, "-p", "同期用", "sync"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error syncing Anki: {e}")
            raise

    def get_stats(self, start_date: datetime.datetime) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        stats_map = {}
        new_counts = {}
        start_ms = int(start_date.timestamp() * 1000)

        with Anki(base_path=self.base_path, profile="同期用") as a:
            # 1. 密度集計
            query = """
                SELECT 
                    (r.id / (1000 * 1800)) * 1800 as bucket_start,
                    c.did,
                    count(*) as count
                FROM revlog r
                JOIN cards c ON r.cid = c.id
                WHERE r.id > ?
                GROUP BY bucket_start, c.did
            """
            rows = a.col.db.all(query, start_ms)
            deck_id_to_name = {v: k for k, v in a.deck_name_to_id.items()}

            for bucket_ts, did, count in rows:
                deck_name = deck_id_to_name.get(did, f"Unknown({did})")
                parent_deck = self._get_parent_deck(deck_name)
                
                if parent_deck:
                    dt_str = datetime.datetime.fromtimestamp(bucket_ts).strftime("%Y-%m-%d %H:%M")
                    key = (dt_str, parent_deck)
                    if key not in stats_map:
                        stats_map[key] = {"count": 0}
                    stats_map[key]["count"] += count

            stats = []
            for (time_str, deck), data in sorted(stats_map.items()):
                stats.append({
                    "time": time_str,
                    "deck": deck,
                    "count": data["count"]
                })

            # 2. ターゲットデッキの進捗
            for deck_name in config.TARGET_DECKS:
                new_cards = a.col.find_cards(f'deck:"{deck_name}" is:new')
                query_today_new = """
                    SELECT count(distinct cid)
                    FROM revlog
                    WHERE id > ? AND type = 0
                    AND cid IN (SELECT id FROM cards WHERE did IN (
                        SELECT id FROM decks WHERE name = ? OR name LIKE ?
                    ))
                """
                today_new_count = a.col.db.scalar(query_today_new, start_ms, deck_name, f"{deck_name}::%")
                
                new_counts[deck_name] = {
                    "remaining_new": len(new_cards),
                    "today_actual_new": today_new_count
                }

        return stats, new_counts

    def _get_parent_deck(self, deck_name: str) -> str | None:
        for track in config.DECKS_TO_TRACK:
            if deck_name == track or deck_name.startswith(f"{track}::"):
                return track
        return None
