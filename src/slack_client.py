import datetime
import logging
import requests
import calendar
from typing import Dict, Any
from .config import config

logger = logging.getLogger(__name__)

class SlackClient:
    def __init__(self):
        self.webhook_url = config.SLACK_WEBHOOK_URL

    def notify_progress(self, new_counts: Dict[str, Any]) -> None:
        now = datetime.datetime.now()
        last_day = calendar.monthrange(now.year, now.month)[1]
        remaining_days = max(1, last_day - now.day + 1)
        
        messages = []
        should_send = False

        for deck_name, data in new_counts.items():
            remaining = data["remaining_new"]
            actual = data["today_actual_new"]
            required_per_day = (remaining + actual) / remaining_days
            
            status_line = f"*{deck_name}*\n    残り新規: {remaining}枚 / 今月残り: {remaining_days}日 → *目標: {required_per_day:.1f}枚/日*"
            actual_line = f"    本日の進捗: {actual}枚"
            
            if actual < required_per_day:
                diff = required_per_day - actual
                messages.append(f"🔥 {status_line}\n{actual_line} (あと {diff:.1f} 枚不足しています。学習を再開しましょう！)")
                should_send = True
            else:
                messages.append(f"✨ {status_line}\n{actual_line} (順調です！この調子で継続しましょう。)")

        if not messages:
            return

        # 時間帯に応じたタイトルを設定
        time_titles = {
            12: "☀️ *昼の進捗確認*",
            17: "🌇 *夕方の進捗確認*",
            21: "🌌 *夜の進捗レポート*",
            23: "🌙 *一日の最終確認*"
        }
        title = time_titles.get(now.hour, "📊 *Anki学習進捗レポート*")
        
        full_message = f"{title}\n" + "\n".join(messages)
        logger.info(f"Sending Slack notification:\n{full_message}")
        self._send(full_message)

    def _send(self, text: str) -> None:
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set. Skipping.")
            return
        try:
            response = requests.post(self.webhook_url, json={"text": text}, timeout=10)
            response.raise_for_status()
            logger.info(f"Slack notification sent successfully (status: {response.status_code})")
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
