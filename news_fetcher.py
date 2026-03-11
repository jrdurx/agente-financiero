import os
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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=data)

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)

def get_rsi_reading(rsi):
    if rsi is None:
        return "Sin datos suficientes"
    if rsi >= 70:
        return "Sobrecompra - posible correccion"
    elif rsi <= 30:
        return "Sobreventa - posible rebote"
    else:
        return "Neutro"

def clean_text(text, max_length=150):
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_length:
        return text
    text = text[:max_length]
    last_space = text.rfind(' ')
    if last_space > max_length * 0.7:
        text = text[:last_space]
    return text + "..."

def get_stock_data(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")
        
        if len(hist) < 2:
            return None
        
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_price) / prev_price) * 100
        
        prices = hist['Close'].values
        rsi = calculate_rsi(prices)
        rsi_reading = get_rsi_reading(rsi)
        
        trend = "Subida" if change_pct > 0 else "Bajada"
        
        return {
            'name': name,
            'price': round(current_price, 2),
            'change': round(change_pct, 2),
            'trend': trend,
            'rsi': rsi,
            'rsi_reading': rsi_reading
        }
    except:
        return None

def get_index_data(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2d")
        
        if len(hist) < 2:
            return {'name': name, 'change': 0, 'trend': ''}
        
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_price) / prev_price) * 100
        
        trend = "Subida" if change_pct > 0 else "Bajada"
        
        return {
            'name': name,
            'price': round(current_price, 2),
            'change': round(change_pct, 2),
            'trend': trend
        }
    except:
        return {'name': name, 'change': 0, 'trend': ''}

def get_crypto_price(symbol, name):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if symbol in data:
                price = data[symbol]['usd']
                change = data[symbol]['usd_24h_change']
                
                url_history = f"https://api.coingecko.com/api/v3/coins/{symbol}/market_chart?vs_currency=usd&days=30"
                r2 = requests.get(url_history, timeout=10)
                rsi = None
                if r2.status_code == 200:
                    prices = [p[1] for p in r2.json()['prices']]
                    rsi = calculate_rsi(np.array(prices))
                
                rsi_reading = get_rsi_reading(rsi)
                trend = "Subida" if change > 0 else "Bajada"
                
                return {
                    'name': name,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'trend': trend,
                    'rsi': rsi,
                    'rsi_reading': rsi_reading
                }
    except:
        pass
    return None

def get_market_news():
    news = []
    seen = set()
    
    try:
        url = "https://api.mediastack.com/v1/news?access_key=deb5b72d2bc5b08dbd2f9f2d3d4a5b6c&categories=business&languages=es&limit=10"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for item in data.get('data', [])[:5]:
                title = item.get('title', '')
                if title and title not in seen and title.lower() != 'null':
                    seen.add(title)
                    news.append({
                        'title': title,
                        'description': clean_text(item.get('description', '')),
                        'source': item.get('source', 'Fuente')
                    })
    except:
        pass
    
    if len(news) < 3:
        try:
            url = "https://news.google.com/rss/search?q=economia+bolsa+acciones&hl=es-ES&gl=ES&ceid=ES:es"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.text)
                for item in root.findall('.//item')[:5]:
                    title = item.findtext('title', '')
                    if title and title not in seen:
                        seen.add(title)
                        news.append({
                            'title': title,
                            'description': clean_text(item.findtext('description', '')),
                            'source': 'Google News'
                        })
        except:
            pass
    
    return news[:5]

def get_crypto_news():
    news = []
    seen = set()
    
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=ES"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            for item in r.json().get('Data', [])[:5]:
                title = item.get('title', '')
                if title and title not in seen:
                    seen.add(title)
                    news.append({
                        'title': title,
                        'description': clean_text(item.get('body', '')),
                        'source': item.get('source_info', {}).get('name', 'CryptoCompare')
                    })
    except:
        pass
    
    return news[:5]

def get_john_economist_video():
    try:
        import urllib.request
        url = "https://www.youtube.com/@JohnEconomist/videos"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=10)
        data = response.read().decode('utf-8')
        
        match = re.search(r'"videoId":"([^"]+)","title":"([^"]+)","thumbnail"', data)
        if match:
            video_id = match.group(1)
            title = match.group(2).replace('\\u0026', '&').replace('\\"', '"')
            return {
                'title': title,
                'url': f"https://www.youtube.com/watch?v={video_id}"
            }
    except Exception as e:
        pass
    
    try:
        url = "https://www.youtube.com/results?search_query=John+Economist"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.text
            match = re.search(r'"videoId":"([^"]+)","title":"([^"]+)","length"', data)
            if match:
                video_id = match.group(1)
                title = match.group(2).replace('\\u0026', '&')
                return {
                    'title': title,
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                }
    except:
        pass
    return None

def generate_conclusion(market_news, crypto_news, indices, cryptos):
    conclusions = []
    
    positive = sum(1 for i in indices if i['change'] > 0)
    negative = len(indices) - positive
    
    if positive > negative:
        conclusions.append("Dia positivo en mercados.")
    elif negative > positive:
        conclusions.append("Dia negativo en mercados.")
    else:
        conclusions.append("Mercados laterales hoy.")
    
    crypto_pos = sum(1 for c in cryptos if c['change'] > 0) if cryptos else 0
    if crypto_pos > len(cryptos) / 2:
        conclusions.append("Criptomonedas muestran fuerza.")
    elif crypto_pos < len(cryptos) / 2 and crypto_pos > 0:
        conclusions.append("Criptomonedas bajo presion.")
    
    return " ".join(conclusions)

def format_message(market_news, crypto_news, stocks, indices, cryptos, video):
    now = datetime.now(SPAIN_TZ).strftime("%d/%m/%Y")
    
    msg = f"📊 *INFORME DIARIO - ECONOMIA Y MERCADOS* | {now}\n\n"
    msg += "─────────────────────\n\n"
    
    msg += "📰 *NOTICIAS ECONOMICAS - MERCADOS*\n\n"
    for i, item in enumerate(market_news, 1):
        msg += f"*• {i:02d}. {item['title'][:65]}*\n"
        if item.get('description'):
            msg += f"   {item['description']}\n\n"
        msg += f"   Fuente: {item['source']}\n\n"
    
    msg += "─────────────────────\n\n"
    
    msg += "📰 *NOTICIAS ECONOMICAS - CRIPTO*\n\n"
    for i, item in enumerate(crypto_news, 1):
        msg += f"*• {i:02d}. {item['title'][:65]}*\n"
        if item.get('description'):
            msg += f"   {item['description']}\n\n"
        msg += f"   Fuente: {item['source']}\n\n"
    
    msg += "─────────────────────\n\n"
    msg += "📈 *ANALISIS DE MERCADOS*\n\n"
    
    for stock in stocks:
        msg += f"- {stock['name']}\n"
        msg += f"  Precio: {stock['price']}\n"
        msg += f"  Tendencia: {stock['trend']}\n"
        msg += f"  RSI (14): {stock['rsi']}\n"
        msg += f"  Lectura: {stock['rsi_reading']}\n\n"
    
    msg += "─────────────────────\n\n"
    msg += "📊 *RESUMEN DE INDICES*\n\n"
    
    for idx in indices:
        sign = "+" if idx['change'] > 0 else ""
        trend_text = f"({idx['trend']})" if idx['trend'] else ""
        msg += f"• {idx['name']} -> {sign}{idx['change']}% {trend_text}\n"
    
    msg += "\n─────────────────────\n\n"
    msg += "📈 *ANALISIS CRIPTO*\n\n"
    
    for crypto in cryptos:
        msg += f"- {crypto['name']}\n"
        msg += f"  Precio: {crypto['price']} $\n"
        msg += f"  Tendencia: {crypto['trend']}\n"
        if crypto.get('rsi'):
            msg += f"  RSI (14): {crypto['rsi']}\n"
            msg += f"  Lectura: {crypto['rsi_reading']}\n"
        msg += "\n"
    
    msg += "─────────────────────\n\n"
    
    conclusion = generate_conclusion(market_news, crypto_news, indices, cryptos)
    msg += f"🧠 *CONCLUSION DEL DIA*\n{conclusion}\n\n"
    msg += "─────────────────────\n\n"
    
    msg += "🎬 *JOHN ECONOMIST*\n"
    if video:
        msg += f"{video['title']}\n"
        msg += f"{video['url']}\n"
    else:
        msg += "No hay nuevo video esta semana.\n"
    
    return msg

def main():
    market_news = get_market_news()
    crypto_news = get_crypto_news()
    
    stocks = [
        get_stock_data("VWCE.MI", "Amundi Index MSCI World AE Acc"),
        get_stock_data("NVDA", "NVIDIA")
    ]
    stocks = [s for s in stocks if s]
    
    indices = [
        get_index_data("^GSPC", "S&P 500"),
        get_index_data("^IXIC", "NASDAQ 100"),
        get_index_data("^IBEX", "IBEX 35"),
        get_index_data("^STOXX", "STOXX EUROPE 600")
    ]
    
    cryptos = [
        get_crypto_price("bitcoin", "Bitcoin"),
        get_crypto_price("ethereum", "Ethereum"),
        get_crypto_price("ripple", "Ripple")
    ]
    cryptos = [c for c in cryptos if c]
    
    video = get_john_economist_video()
    
    message = format_message(market_news, crypto_news, stocks, indices, cryptos, video)
    send_telegram(message)

if __name__ == "__main__":
    main()
