import os
import requests
import json
from datetime import datetime, timezone
import pytz

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SPAIN_TZ = pytz.timezone('Europe/Madrid')

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=data)

def get_yahoo_news():
    url = "https://newsdata.io/api/1/news?apikey=pub_demo&q=economia%20OR%20bolsa%20OR%20criptomonedas&language=es&category=business"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get('results', [])[:10]
    except:
        pass
    return []

def get_coinnews():
    url = "https://min-api.cryptocompare.com/data/v2/news/?lang=ES"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json().get('Data', [])
            news = []
            for item in data[:5]:
                news.append({
                    'title': item.get('title', ''),
                    'description': item.get('body', '')[:200],
                    'source': item
