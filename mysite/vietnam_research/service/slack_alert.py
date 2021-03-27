import json
from stripe.http_client import requests


def send_message(message: str):
    response = requests.post(
        'https://hooks.slack.com/services/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',
        data=json.dumps({
            "channel": "random",
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
