import json
import os

import requests

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