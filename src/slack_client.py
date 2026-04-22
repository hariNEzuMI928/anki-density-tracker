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
        
        # デッキごとのアイコン設定
        deck_icons = {
            "2_EnglishComposition": "📘",
            "3_FluencyTest": "📙",
            "1_Vocabulary": "📕"
        }

        for deck_name, data in new_counts.items():
            remaining = data["remaining_new"]
            actual = data["today_actual_new"]
            required_per_day = (remaining + actual) / remaining_days
            
            # 達成率の計算
            percent = (actual / required_per_day * 100) if required_per_day > 0 else 0
            
            # プログレスバーの生成 (10個の絵文字)
            filled_count = min(10, int(percent / 10))
            bar = "🟢" * filled_count + "⚪️" * (10 - filled_count)
            
            # デッキアイコンの取得
            icon = deck_icons.get(deck_name, "✨")
            
            # ステータス判定
            if actual < required_per_day:
                diff = required_per_day - actual
                status_text = f"🔥 *Status: あと {diff:.1f} 枚不足しています。再開しましょう！*"
            else:
                status_text = "🔥 *Status: 順調です！この調子で継続しましょう。*"

            deck_msg = (
                f"{icon} *{deck_name}*\n"
                f"{bar} ({percent:.0f}%)\n"
                f"📈 進捗: *{actual}* / 目標: {required_per_day:.1f} 枚\n"
                f"⏳ 残り: {remaining}枚 (今月あと{remaining_days}日)\n"
                f"{status_text}"
            )
            messages.append(deck_msg)

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
        
        full_message = f"{title}\n\n" + "\n\n".join(messages)
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
