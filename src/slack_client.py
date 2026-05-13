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

    def notify_progress(self, counts: Dict[str, Any]) -> None:
        now = datetime.datetime.now()
        
        # 今週の日曜日までの残り日数を計算 (月=0, ..., 日=6)
        # 日曜日の場合、残り日数は1(今日を含める)とする。それ以外は日曜日までの日数+1(今日)
        days_until_sunday = 6 - now.weekday()
        remaining_days = days_until_sunday + 1 if days_until_sunday > 0 else 1
        
        messages = []
        
        # デッキごとのアイコン設定
        deck_icons = {
            "2_EnglishComposition": "📘",
            "3_FluencyTest": "📙",
            "1_Vocabulary": "📕"
        }

        for deck_name, data in counts.items():
            remaining_due = data["remaining_due"]
            today_reviewed = data["today_reviewed"]
            
            # 日曜日までに0にするために、1日あたりに消化すべき「残りの」枚数
            # (厳密には明日以降増える期日カードもあるが、現在の残数ベースで計算)
            required_per_day = remaining_due / remaining_days
            
            # デッキアイコンの取得
            icon = deck_icons.get(deck_name, "✨")
            
            # ステータス判定
            if remaining_due > 0:
                status_text = f"🔥 *Status: 日曜日までに完済するには、あと1日あたり約 {required_per_day:.1f} 枚の消化が必要です！*"
            else:
                status_text = "✨ *Status: 期日切れカードなし！素晴らしいです！*"

            deck_msg = (
                f"{icon} *{deck_name}*\n"
                f"🚨 期日切れ未完了: *{remaining_due}* 枚\n"
                f"📚 本日の学習済: {today_reviewed} 枚\n"
                f"⏳ 日曜日まで残り {remaining_days} 日\n"
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
