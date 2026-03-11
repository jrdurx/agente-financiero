import os
import sys
import requests
import re
from datetime import datetime
import pytz
import yfinance as yf
import numpy as np

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SPAIN_TZ = pytz.timezone('Europe/Madrid')

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        r = requests.post(url, json=data, timeout=15)
        print(f"Telegram response: {r.status_code}")
    except Exception as e:
        print(f"Error sending telegram: {e}")

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('"', '"')
    return text.strip()

def clean_text(text, max_len=120):
    if not text:
        return ""
    text = clean_html(text).strip()
    if len(text) <= max_len:
        return text
    text = text[:max_len]
    last_space = text.rfind(' ')
    if last_space > max_len * 0.6:
        text = text[:last_space]
    return text + "..."

def calculate_rsi(prices, period=14):
    if prices is None or len(prices) < period + 1:
        return None
    try:
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)
    except:
        return None

def get_rsi_label(rsi):
    if rsi is None:
        return "Sin datos"
    if rsi >= 70:
        return "Sobrecompra"
    if rsi <= 30:
        return "Sobreventa"
    return "Neutro"

def get_stock(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty or len(hist) < 2:
            return None
        price = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        change = ((price - prev) / prev) * 100
        prices_arr = hist['Close'].values
        rsi = calculate_rsi(prices_arr)
        return {
            'name': name,
            'price': round(price, 2),
            'change': round(change, 2),
            'trend': "Subida" if change > 0 else "Bajada",
            'rsi': rsi,
            'rsi_label': get_rsi_label(rsi)
        }
    except Exception as e:
        print(f"Error getting {ticker}: {e}")
        return None

def get_index(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty or len(hist) < 2:
            return {'name': name, 'change': 0, 'trend': ''}
        price = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        change = ((price - prev) / prev) * 100
        return {
            'name': name,
            'change': round(change, 2),
            'trend': "Subida" if change > 0 else "Bajada"
        }
    except:
        return {'name': name, 'change': 0, 'trend': ''}

def get_crypto(sym, name):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={sym}&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if sym not in data:
            return None
        price = data[sym]['usd']
        change = data[sym]['usd_24h_change']
        
        rsi = None
        try:
            r2 = requests.get(f"https://api.coingecko.com/api/v3/coins/{sym}/market_chart?vs_currency=usd&days=30", timeout=10)
            if r2.status_code == 200:
                prices = [p[1] for p in r2.json()['prices']]
                rsi = calculate_rsi(np.array(prices))
        except:
            pass
        
        return {
            'name': name,
            'price': round(price, 2),
            'change': round(change, 2),
            'trend': "Subida" if change > 0 else "Bajada",
            'rsi': rsi,
            'rsi_label': get_rsi_label(rsi)
        }
    except:
        return None

def get_market_news():
    news = []
    seen = set()
    try:
        r = requests.get("https://feeds.finance.yahoo.com/rss/headline?s=^GSPC,^IXIC,^DJI", timeout=10)
        if r.status_code == 200:
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(r.text)
                for item in root.findall('.//item')[:5]:
                    title = item.findtext('title', '')
                    if title and title not in seen:
                        seen.add(title)
                        desc = clean_text(item.findtext('description', ''))
                        news.append({'title': title[:70], 'desc': desc, 'source': 'Yahoo Finance'})
            except:
                pass
    except:
        pass
    
    if len(news) < 3:
        try:
            r = requests.get("https://news.google.com/rss/search?q=economia+bolsa&hl=es-ES", timeout=10)
            if r.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.text)
                for item in root.findall('.//item')[:5]:
                    title = item.findtext('title', '')
                    if title and title not in seen:
                        seen.add(title)
                        news.append({'title': title[:70], 'desc': clean_text(item.findtext('description', '')), 'source': 'Google News'})
        except:
            pass
    
    return news[:5]

def get_crypto_news():
    news = []
    seen = set()
    try:
        r = requests.get("https://min-api.cryptocompare.com/data/v2/news/?lang=ES", timeout=10)
        if r.status_code == 200:
            for item in r.json().get('Data', [])[:5]:
                title = item.get('title', '')
                if title and title not in seen:
                    seen.add(title)
                    news.append({'title': title[:70], 'desc': clean_text(item.get('body', '')), 'source': item.get('source_info', {}).get('name', 'Crypto')})
    except:
        pass
    return news[:5]

def get_video():
    urls = [
        "https://www.youtube.com/@JohnEconomist/videos",
        "https://www.youtube.com/channel/UCZ4Y6Kk2pNuj3fFK8Y4_2_Aw/videos"
    ]
    for url in urls:
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if r.status_code == 200:
                m = re.search(r'"videoId":"([^"]+)","title":"([^"]+)"', r.text)
                if m:
                    return {'title': m.group(2).replace('\\u0026', '&'), 'url': f"https://www.youtube.com/watch?v={m.group(1)}"}
        except:
            continue
    return None

def make_msg(news, cryptos, stocks, indices, crypton, video):
    now = datetime.now(SPAIN_TZ).strftime("%d/%m/%Y")
    m = f"📊 *INFORME DIARIO - ECONOMIA Y MERCADOS* | {now}\n\n───────────────\n\n"
    m += "📰 *NOTICIAS - MERCADOS*\n\n"
    for i, n in enumerate(news, 1):
        m += f"*{i:02d}. {n['title'][:60]}*\n"
        if n.get('desc'): m += f"   {n['desc']}\n"
        m += f"   ({n['source']})\n\n"
    m += "───────────────\n\n📰 *NOTICIAS - CRIPTO*\n\n"
    for i, n in enumerate(crypton,
