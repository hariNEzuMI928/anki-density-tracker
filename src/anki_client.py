import os
import subprocess
import datetime
import logging
import zoneinfo
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

    def get_maturity_stats(self) -> List[Dict[str, Any]]:
        maturity_stats = []
        with Anki(base_path=self.base_path, profile="同期用") as a:
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            for deck_name in config.DECKS_TO_TRACK:
                # Mature: review cards, not suspended, interval >= 21
                mature_cards = a.col.find_cards(f'deck:"{deck_name}" is:review -is:suspended prop:ivl>=21')
                # Young: review cards, not suspended, interval < 21
                young_cards = a.col.find_cards(f'deck:"{deck_name}" is:review -is:suspended prop:ivl<21')
                
                maturity_stats.append({
                    "date": today_str,
                    "deck": deck_name,
                    "young": len(young_cards),
                    "mature": len(mature_cards)
                })
        return maturity_stats

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
                due_cards = a.col.find_cards(f'deck:"{deck_name}" is:due')
                query_today_reviewed = """
                    SELECT count(distinct cid)
                    FROM revlog
                    WHERE id > ?
                    AND cid IN (SELECT id FROM cards WHERE did IN (
                        SELECT id FROM decks WHERE name = ? OR name LIKE ?
                    ))
                """
                today_reviewed_count = a.col.db.scalar(query_today_reviewed, start_ms, deck_name, f"{deck_name}::%")
                
                new_counts[deck_name] = {
                    "remaining_due": len(due_cards),
                    "today_reviewed": today_reviewed_count
                }

        return stats, new_counts

    def get_daily_study_time(self) -> List[Dict[str, Any]]:
        tz = zoneinfo.ZoneInfo("Europe/Warsaw")
        now = datetime.datetime.now(tz)
        start_date = now - datetime.timedelta(days=30)
        start_ms = int(start_date.timestamp() * 1000)

        daily_stats_map = {}

        with Anki(base_path=self.base_path, profile="同期用") as a:
            query = """
                SELECT 
                    r.id,
                    c.did,
                    MIN(r.time, 600000) as capped_time
                FROM revlog r
                JOIN cards c ON r.cid = c.id
                WHERE r.id > ?
            """
            rows = a.col.db.all(query, start_ms)
            deck_id_to_name = {v: k for k, v in a.deck_name_to_id.items()}

            for rev_id_ms, did, capped_time in rows:
                rev_time_utc = datetime.datetime.fromtimestamp(rev_id_ms / 1000.0, tz=datetime.timezone.utc)
                rev_time_local = rev_time_utc.astimezone(tz)
                date_str = rev_time_local.strftime("%Y-%m-%d")
                
                deck_name = deck_id_to_name.get(did, f"Unknown({did})")
                parent_deck = self._get_parent_deck(deck_name)
                
                if parent_deck:
                    key = (date_str, parent_deck)
                    if key not in daily_stats_map:
                        daily_stats_map[key] = 0
                    daily_stats_map[key] += capped_time

        stats = []
        for (date_str, deck), total_time_ms in sorted(daily_stats_map.items()):
            minutes = total_time_ms / 60000.0
            stats.append({
                "date": date_str,
                "deck": deck,
                "minutes": round(minutes, 2)
            })

        return stats

    def _get_parent_deck(self, deck_name: str) -> str | None:
        for track in config.DECKS_TO_TRACK:
            if deck_name == track or deck_name.startswith(f"{track}::"):
                return track
        return None
