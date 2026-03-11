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
        return "Sobrecompra - posible corrección"
    elif rsi <= 30:
        return "Sobreventa - posible rebond"
    else:
        return "Neutro"

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
        
        trend = "📈 Subida" if change_pct > 0 else "📉 Bajada"
        
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
            return {'name': name, 'change': 0, 'trend': '➡️'}
        
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_price) / prev_price) * 100
        
        trend = "📈" if change_pct > 0 else "📉"
        
        return {
            'name': name,
            'price': round(current_price, 2),
            'change': round(change_pct, 2),
            'trend': trend
        }
    except:
        return {'name': name, 'change': 0, 'trend': '➡️'}

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
                trend = "📈 Subida" if change > 0 else "📉 Bajada"
                
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
    
    urls = [
        ("https://feeds.finance.yahoo.com/rss/headline?s=^GSPC,^IXIC,^STOXX600&format=xml", "markets"),
        ("https://feeds.finance.yahoo.com/rss/headline?s=BTC-USD,ETH-USD,XRP-USD&format=xml", "crypto"),
    ]
    
    try:
        url = "https://newsdata.io/api/1/news?apikey=pub_demo&q=economia%20OR%20bolsa%20OR%20acciones%20OR%20mercados&language=es&category=business"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            for item in r.json().get('results', [])[:8]:
                title = item.get('title', '')
                if title and title not in seen:
                    seen.add(title)
                    news.append({
                        'title': title,
                        'description': item.get('description', '')[:120],
                        'source': item.get('source_id', 'Fuente')
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
            for item in r.json().get('Data', [])[:8]:
                title = item.get('title', '')
                if title and title not in seen:
                    seen.add(title)
                    news.append({
                        'title': title,
                        'description': item.get('body', '')[:120],
                        'source': item.get('source_info', {}).get('name', 'CryptoCompare')
                    })
    except:
        pass
    
    return news[:5]

def get_john_economist_video():
    url = "https://www.youtube.com/results?search_query=John+Economist&sp=CAI%253D"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.text
            match = re.search(r'"videoId":"([^"]+)","title":"([^"]+)","length', data)
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
        conclusions.append("Día positivo en mercados.")
    elif negative > positive:
        conclusions.append("Día negativo en mercados.")
    else:
        conclusions.append("Mercados laterales hoy.")
    
    crypto_pos = sum(1 for c in cryptos if c['change'] > 0) if cryptos else 0
    if crypto_pos > len(cryptos) / 2:
        conclusions.append("Criptomonedas muestran fuerza.")
    elif crypto_pos < len(cryptos) / 2 and crypto_pos > 0:
        conclusions.append("Criptomonedas bajo presión.")
    
    return " ".join(conclusions)

def format_message(market_news, crypto_news, stocks, indices, cryptos, video):
    now = datetime.now(SPAIN_TZ).strftime("%d/%m/%Y")
    
    msg = f"📊 *INFORME DIARIO – ECONOMÍA Y MERCADOS* | {now}\n"
    msg += "─────────────────────\n\n"
    
    msg += "📰 *NOTICIAS ECONÓMICAS – MERCADOS*\n\n"
    for i, item in enumerate(market_news, 1):
        msg += f"• *{i:02d}. {item['title'][:70]}*\n"
        if item.get('description'):
            msg += f"   {item['description']}\n"
        msg += f"   📰 {item['source']}\n\n"
    
    msg += "─────────────────────\n\n"
    
    msg += "📰 *NOTICIAS ECONÓMICAS – CRIPTO*\n\n"
    for i, item in enumerate(crypto_news, 1):
        msg += f"• *{i:02d}. {item['title'][:70]}*\n"
        if item.get('description'):
            msg += f"   {item['description']}\n"
        msg += f"   📰 {item['source']}\n\n"
    
    msg += "─────────────────────\n\n"
    msg += "📈 *ANÁLISIS DE MERCADOS*\n\n"
    
    for stock in stocks:
        msg += f"*— {stock['name']}*\n"
        msg += f"• Precio: {stock['price']}\n"
        msg += f"• Tendencia: {stock['trend']}\n"
        msg += f"• RSI (14): {stock['rsi']}\n"
        msg += f"• Lectura: {stock['rsi_reading']}\n\n"
    
    msg += "─────────────────────\n\n"
    msg += "📊 *RESUMEN DE ÍNDICES*\n\n"
    
    for idx in indices:
        sign = "+" if idx['change'] > 0 else ""
        msg += f"• {idx['name']} –> {sign}{idx['change']}% {idx['trend']}\n"
    
    msg += "\n─────────────────────\n\n"
    msg += "📈 *ANÁLISIS CRIPTO*\n\n"
    
    for crypto in cryptos:
        msg += f"*— {crypto['name']}*\n"
        msg += f"• Precio: {crypto['price']} $\n"
        msg += f"• Tendencia: {crypto['trend']}\n"
        if crypto.get('rsi'):
            msg += f"• RSI (14): {crypto['rsi']}\n"
            msg += f"• Lectura: {crypto['rsi_reading']}\n"
        msg += "\n"
    
    msg += "─────────────────────\n\n"
    
    conclusion = generate_conclusion(market_news, crypto_news, indices, cryptos)
    msg += f"🧠 *CONCLUSIÓN DEL DÍA*\n{conclusion}\n\n"
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
