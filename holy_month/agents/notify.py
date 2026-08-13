import requests

from holy_month.config import Config


class NotificationAgent:
    def send_telegram(self, message: str) -> bool:
        if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
            print("Telegram not configured. Skipping notification.")
            return False
        try:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": Config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=15)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False
