import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# .env ファイルを読み込む
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TODAY = 0


class SlackService:
    def __init__(self, channel_id, webhook_url):
        self.channel_id = channel_id
        self.webhook_url = webhook_url

    def send_message(self, message: str):
        payload = {
            "channel": self.channel_id,
            "text": message,
            "icon_emoji": ":mostly_sunny:",
            "username": "weather_bot",
        }
        response = requests.post(
            self.webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()


class WeatherService:

    @staticmethod
    def fetch_weather(code: str) -> dict:
        url = f"https://weather.tsukumijima.net/api/forecast/city/{code}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def format_weather_message(weather_data: dict) -> str:
        forecast = weather_data["forecasts"][TODAY]
        lines = [
            weather_data["title"],
            forecast["date"],
            forecast["telop"],
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    """
    このスクリプトを直接実行する場合のメイン処理。

    動作内容:
    - 東京都（city_code: 130010）の天気情報を取得
    - Slackの指定チャンネルに天気情報を送信

    必要な環境変数:
    - SLACK_CHANNEL_ID: SlackのチャンネルID
    - SLACK_WEBHOOK_URL: SlackのWebhook URL

    注意: 
    このスクリプトと同じディレクトリ（lib/slack/）の.envファイルから環境変数を読み込みます。

    PyCharmで実行する場合:
    メニューバー → Run → Edit Configurations... でWorking directoryを
    lib/slack/ に設定してください。Working directoryがズレていると
    .envファイルが正しく読み込まれずに実行に失敗します。
    """
    city_code = "130010"
    slack_service = SlackService(
        channel_id=os.getenv("SLACK_CHANNEL_ID"),
        webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
    )
    weather_service = WeatherService()
    slack_service.send_message(
        message=weather_service.format_weather_message(
            weather_data=weather_service.fetch_weather(city_code)
        )
    )
