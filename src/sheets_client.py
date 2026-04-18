import os
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import List, Dict, Any
from .config import config

logger = logging.getLogger(__name__)

class SheetsClient:
    def __init__(self):
        self.scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        self.header = ["日時", "デッキ", "枚数"]

    def _get_sheet(self):
        if not config.SPREADSHEET_ID or not config.CREDENTIALS_PATH.exists():
            return None
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(config.CREDENTIALS_PATH), self.scope)
        client = gspread.authorize(creds)
        return client.open_by_key(config.SPREADSHEET_ID).worksheet("Anki")

    def update_stats(self, stats: List[Dict[str, Any]]) -> None:
        sheet = self._get_sheet()
        if not sheet:
            logger.warning("Google Sheets config missing. Skipping.")
            return

        all_values = sheet.get_all_values()
        if not all_values or all_values[0][0] != self.header[0]:
            sheet.insert_row(self.header, 1)
            all_values = [self.header] + all_values

        existing_data = {(row[0], row[1]): i for i, row in enumerate(all_values, 1) if len(row) >= 2}
        new_rows = []
        updates = []

        for item in stats:
            key = (item["time"], item["deck"])
            new_row = [item["time"], item["deck"], item["count"]]
            if key in existing_data:
                idx = existing_data[key]
                curr_row = all_values[idx-1]
                if len(curr_row) < 3 or str(curr_row[2]) != str(item["count"]):
                    updates.append({"range": f"A{idx}:C{idx}", "values": [new_row]})
            else:
                new_rows.append(new_row)

        if updates:
            sheet.batch_update(updates)
        if new_rows:
            sheet.append_rows(new_rows)
        
        logger.info(f"Sheets: {len(new_rows)} new, {len(updates)} updated.")
