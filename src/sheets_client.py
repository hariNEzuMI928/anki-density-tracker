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

    def _get_sheet(self, sheet_name: str = "Anki"):
        if not config.SPREADSHEET_ID or not config.CREDENTIALS_PATH.exists():
            return None
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(config.CREDENTIALS_PATH), self.scope)
        client = gspread.authorize(creds)
        try:
            return client.open_by_key(config.SPREADSHEET_ID).worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            # Optionally create it if needed, but user said it's created.
            logger.error(f"Worksheet {sheet_name} not found.")
            return None

    def update_stats(self, stats: List[Dict[str, Any]]) -> None:
        sheet = self._get_sheet()
        if not sheet:
            logger.warning("Google Sheets config missing. Skipping.")
            return

        all_values = sheet.get_all_values()
        if not all_values or not all_values[0] or all_values[0][0] != self.header[0]:
            sheet.insert_row(self.header, 1)
            all_values = [self.header] + (all_values if all_values and all_values[0] else [])

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

    def update_maturity_stats(self, maturity_stats: List[Dict[str, Any]]) -> None:
        sheet = self._get_sheet("Anki_Matured")
        if not sheet:
            logger.warning("Anki_Matured worksheet not found or config missing. Skipping.")
            return

        header = ["date", "deck", "young", "mature"]
        all_values = sheet.get_all_values()
        if not all_values or not all_values[0] or all_values[0][0] != header[0]:
            sheet.insert_row(header, 1)
            all_values = [header] + (all_values if all_values and all_values[0] else [])

        existing_data = {(row[0], row[1]): i for i, row in enumerate(all_values, 1) if len(row) >= 2}
        new_rows = []
        updates = []

        for item in maturity_stats:
            key = (item["date"], item["deck"])
            new_row = [item["date"], item["deck"], item["young"], item["mature"]]
            if key in existing_data:
                idx = existing_data[key]
                updates.append({"range": f"A{idx}:D{idx}", "values": [new_row]})
            else:
                new_rows.append(new_row)

        if updates:
            sheet.batch_update(updates)
        if new_rows:
            sheet.append_rows(new_rows)
        
        logger.info(f"Maturity Sheets: {len(new_rows)} new, {len(updates)} updated.")
