import os
import sys
import subprocess
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from apyanki.anki import Anki
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# 設定
DECKS_TO_TRACK = ["1_Vocabulary", "2_EnglishComposition", "3_FluencyTest"]
TARGET_DECKS = ["2_EnglishComposition", "3_FluencyTest"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")
ANKI_BASE = os.path.expanduser("~/Library/Application Support/Anki2")

def is_anki_running():
    try:
        output = subprocess.check_output(["pgrep", "-x", "Anki"], stderr=subprocess.STDOUT)
        return len(output) > 0
    except subprocess.CalledProcessError:
        return False

def sync_anki():
    print("Syncing Anki...")
    try:
        # apy sync コマンドを呼び出す。ANKI_BASE 環境変数を明示的に渡す
        env = os.environ.copy()
        env["ANKI_BASE"] = ANKI_BASE
        subprocess.run(["apy", "sync"], check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error syncing Anki: {e}")
        # 同期エラーでもローカルデータで続行可能な場合は続行するが、ここでは終了
        sys.exit(1)

def get_anki_stats():
    stats_map = {}  # (time, parent_deck) -> {count, duration}
    new_counts = {}

    # 今日の開始（ローカル時間）
    now = datetime.datetime.now()
    today_start = datetime.datetime(now.year, now.month, now.day)
    today_start_ms = int(today_start.timestamp() * 1000)

    with Anki(base_path=ANKI_BASE) as a:
        # 1. 密度集計 (30分バケット)
        query = """
            SELECT
                (r.id / (1000 * 1800)) * 1800 as bucket_start,
                c.did,
                count(*) as count,
                sum(r.time) / 1000.0 as duration_sec
            FROM revlog r
            JOIN cards c ON r.cid = c.id
            WHERE r.id > ?
            GROUP BY bucket_start, c.did
        """
        rows = a.col.db.all(query, today_start_ms)

        # デッキIDから名前へのマッピング
        deck_id_to_name = {v: k for k, v in a.deck_name_to_id.items()}

        for bucket_ts, did, count, duration in rows:
            deck_name = deck_id_to_name.get(did, f"Unknown({did})")

            # 親デッキの特定
            parent_deck = None
            for track in DECKS_TO_TRACK:
                if deck_name == track or deck_name.startswith(f"{track}::"):
                    parent_deck = track
                    break

            if parent_deck:
                dt_str = datetime.datetime.fromtimestamp(bucket_ts).strftime("%Y-%m-%d %H:%M")
                key = (dt_str, parent_deck)
                if key not in stats_map:
                    stats_map[key] = {"count": 0, "duration": 0}
                stats_map[key]["count"] += count
                stats_map[key]["duration"] += duration

        # 辞書からリストに変換
        stats = []
        for (time_str, deck), data in sorted(stats_map.items()):
            stats.append({
                "time": time_str,
                "deck": deck,
                "count": data["count"],
                "duration": round(data["duration"] / 60.0, 2)
            })

        # 2. ターゲットデッキの新規カード数と本日の新規着手実績
        for deck_name in TARGET_DECKS:
            # 残り新規カード数
            new_cards = a.col.find_cards(f'deck:"{deck_name}" is:new')
            # 本日新規に着手したカード数
            query_today_new = """
                SELECT count(distinct cid)
                FROM revlog
                WHERE id > ? AND type = 0
                AND cid IN (SELECT id FROM cards WHERE did IN (
                    SELECT id FROM decks WHERE name = ? OR name LIKE ?
                ))
            """
            deck_id = a.deck_name_to_id.get(deck_name)
            today_new_count = a.col.db.scalar(query_today_new, today_start_ms, deck_name, f"{deck_name}::%")

            new_counts[deck_name] = {
                "remaining_new": len(new_cards),
                "today_actual_new": today_new_count
            }

    return stats, new_counts

def update_google_sheets(stats):
    if not SPREADSHEET_ID or not os.path.exists(CREDENTIALS_PATH):
        print("Google Sheets config missing. Skipping.")
        return

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Anki")

        # ヘッダーチェック（1行目の1列目が「日時」でなければ挿入）
        first_row = sheet.row_values(1)
        header = ["日時", "デッキ", "枚数"]
        if not first_row or first_row[0] != header[0]:
            sheet.insert_row(header, 1)
            print("Inserted header row.")
            all_values = [header] + sheet.get_all_values()
        else:
            all_values = sheet.get_all_values()

        # 既存データのインデックス化 (日時, デッキ) -> 行番号(1-based)
        existing_data = {}
        for i, row in enumerate(all_values, 1):
            if len(row) >= 2:
                existing_data[(row[0], row[1])] = i

        new_entries_count = 0
        updated_entries_count = 0
        new_rows = []
        updates = []

        for item in stats:
            key = (item["time"], item["deck"])
            new_row = [item["time"], item["deck"], item["count"]]
            if key in existing_data:
                row_idx = existing_data[key]
                curr_row = all_values[row_idx-1]
                if (len(curr_row) < 3 or str(curr_row[2]) != str(item["count"])):
                    updates.append({"range": f"A{row_idx}:C{row_idx}", "values": [new_row]})
                    updated_entries_count += 1
            else:
                new_rows.append(new_row)
                new_entries_count += 1

        # バッチ更新の実行
        if updates:
            sheet.batch_update(updates)
        if new_rows:
            sheet.append_rows(new_rows)

        if new_entries_count > 0 or updated_entries_count > 0:
            print(f"Google Sheets: {new_entries_count} new, {updated_entries_count} updated (Batch).")
        else:
            print("Google Sheets: No changes needed.")
    except Exception as e:
        print(f"Error updating Google Sheets: {e}")


def process_notifications(new_counts):
    now = datetime.datetime.now()
    # 今月末
    import calendar
    last_day = calendar.monthrange(now.year, now.month)[1]
    remaining_days = max(1, last_day - now.day + 1)

    messages = []
    should_notify = False

    for deck_name, data in new_counts.items():
        remaining = data["remaining_new"]
        actual = data["today_actual_new"]
        required_per_day = (remaining + actual) / remaining_days

        status_line = f"*{deck_name}*\n    残り新規: {remaining}枚 / 今月残り: {remaining_days}日 → *目標: {required_per_day:.1f}枚/日*"
        actual_line = f"    本日の進捗: {actual}枚"

        if actual < required_per_day:
            diff = required_per_day - actual
            messages.append(f"🔥 {status_line}\n{actual_line} (あと {diff:.1f} 枚不足しています。)")
            should_notify = True
        else:
            messages.append(f"✨ {status_line}\n{actual_line} (順調です！この調子で継続しましょう。)")

    if messages:
        full_message = "📊 *Anki学習進捗レポート*\n" + "\n".join(messages)

        print(full_message)
        # 21時以降の場合、または強制通知フラグがある場合に送信
        if now.hour >= 21 or os.environ.get("FORCE_NOTIFY"):
            send_slack_notification(full_message)

def send_slack_notification(message):
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set. Skipping Slack notification.")
        return
    try:
        payload = {"text": message}
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending Slack notification: {e}")

def main():
    if is_anki_running():
        print("Anki is running. Skipping to avoid DB lock.")
        return

    # apy sync はネットワーク状況に依存するため、失敗しても集計は試みる
    try:
        sync_anki()
    except Exception as e:
        print(f"Sync failed, continuing with local data: {e}")

    stats, new_counts = get_anki_stats()

    if stats:
        update_google_sheets(stats)

    process_notifications(new_counts)

    print("Process completed.")

if __name__ == "__main__":
    main()
