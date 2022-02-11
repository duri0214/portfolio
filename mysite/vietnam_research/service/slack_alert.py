import json
import os
import requests


def send_message(message: str):
    channel_id = 'C8TG6TW6B'
    response = requests.post(
        os.environ.get('SLACK_WEBHOOK_URL'),
        data=json.dumps({
            "channel": channel_id,
            "text": message,
            "icon_emoji": ":mostly_sunny:",
            "username": "weather_bot"
        })
    )
    print(response)


if __name__ == '__main__':
    TODAY = 0
    TOKYO = 130010
    url = f'https://weather.tsukumijima.net/api/forecast/city/{TOKYO}'
    weather_data = requests.get(url).json()
    txt = weather_data["title"] + '\n'
    txt += weather_data["forecasts"][TODAY]["date"] + '\n'
    txt += weather_data["forecasts"][TODAY]["telop"] + '\n'
    send_message(txt)
