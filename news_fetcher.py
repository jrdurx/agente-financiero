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
    text = text.replace('&quot;', '"')
    return text.strip()

def clean_text(text, max_len=150):
    if not text:
        return ""
    text = clean_html(text).strip()
    text = re.sub(r'\s+', ' ', text)
    
    # Take first sentence as fallback
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if sentences:
        first_sent = sentences[0]
        if len(first_sent) <= max_len:
            return first_sent
        first_sent = first_sent[:max_len]
        last_space = first_sent.rfind(' ')
        if last_space > max_len * 0.6:
            first_sent = first_sent[:last_space]
        return first_sent + "..."
    
    text = text[:max_len]
    last_space = text.rfind(' ')
    if last_space > max_len * 0.6:
        text = text[:last_space]
    return text + "..."

HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')

def summarize_with_ai(text, max_lines=6):
    """Resume un texto usando resumen extractivo (sin API externa)"""
    if not text:
        return ""
    
    try:
        # Resumen extractivo: tomar las oraciones más importantes
        text = clean_html(text).strip()
        text = re.sub(r'\s+', ' ', text)
        
        # Dividir en oraciones
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return clean_text(text, 150)
        
        # Calcular puntuación por oración (más larga = más importante)
        scored = []
        for i, sent in enumerate(sentences):
            # Puntuación basada en longitud y posición (priorizar las primeras)
            score = len(sent) * (1 + 0.5 / (i + 1))
            scored.append((sent, score))
        
        # Ordenar por puntuación
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Tomar las oraciones más importantes
        num_sentences = min(6, len(sentences))
        selected = [s[0] for s in scored[:num_sentences]]
        
        # Reconstruir el resumen manteniendo orden original
        final_sentences = []
        for sent in sentences:
            if sent in selected and sent not in final_sentences:
                final_sentences.append(sent)
        
        # Si no hay suficientes, añadir del sorted
        if len(final_sentences) < num_sentences:
            for sent, _ in scored:
                if sent not in final_sentences:
                    final_sentences.append(sent)
                if len(final_sentences) >= num_sentences:
                    break
        
        # Unir las oraciones
        summary = ". ".join(final_sentences[:num_sentences])
        if not summary.endswith('.'):
            summary += "."
        
        return summary
        
    except Exception as e:
        print(f"Error en resumen: {e}")
        return clean_text(text, 150)

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
                        raw_desc = item.findtext('description', '')
                        desc = summarize_with_ai(raw_desc) if raw_desc else ""
                        news.append({'title': title, 'desc': desc, 'source': 'Yahoo Finance'})
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
                        raw_desc = item.findtext('description', '')
                        desc = summarize_with_ai(raw_desc) if raw_desc else ""
                        news.append({'title': title, 'desc': desc, 'source': 'Google News'})
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
                    raw_desc = item.get('body', '')
                    desc = summarize_with_ai(raw_desc) if raw_desc else ""
                    news.append({'title': title, 'desc': desc, 'source': item.get('source_info', {}).get('name', 'Crypto')})
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
    m = f"📊 *INFORME DIARIO - ECONOMIA Y MERCADOS* | {now}\n\n────────────────\n\n"
    m += "📰 *NOTICIAS - MERCADOS*\n\n"
    for i, n in enumerate(news, 1):
        m += f"*{i:02d}. {n['title']}*\n\n"
        if n.get('desc'): m += f"   {n['desc']}\n\n"
        m += f"   Fuente: {n['source']}\n\n"
    m += "────────────────\n\n📰 *NOTICIAS - CRIPTO*\n\n"
    for i, n in enumerate(crypton, 1):
        m += f"*{i:02d}. {n['title']}*\n\n"
        if n.get('desc'): m += f"   {n['desc']}\n\n"
        m += f"   Fuente: {n['source']}\n\n"
    m += "────────────────\n\n📈 *ANALISIS MERCADOS*\n\n"
    for s in stocks:
        m += f"- {s['name']}\n  Precio: {s['price']} | Cambio: {s['change']}% ({s['trend']})\n  RSI: {s['rsi']} - {s['rsi_label']}\n\n"
    m += "📊 *INDICES*\n\n"
    for i in indices:
        s = "+" if i['change'] > 0 else ""
        m += f"• {i['name']}: {s}{i['change']}% ({i['trend']})\n"
    m += "\n────────────────\n\n📈 *ANALISIS CRIPTO*\n\n"
    for c in cryptos:
        m += f"- {c['name']}: {c['price']}$ ({c['change']}% {c['trend']})\n"
        if c.get('rsi'): m += f"  RSI: {c['rsi']} - {c['rsi_label']}\n"
        m += "\n"
    m += "────────────────\n\n🧠 *CONCLUSION*\n"
    pos = sum(1 for i in indices if i['change'] > 0)
    m += "Dia positivo en mercados.\n" if pos > 2 else "Dia negativo en mercados.\n" if pos < 2 else "Mercados laterales.\n"
    cpos = sum(1 for c in cryptos if c['change'] > 0)
    m += "Criptos al alza.\n" if cpos > 1 else "Criptos a la baja.\n"
    m += "────────────────\n\n🎬 *JOHN ECONOMIST*\n"
    if video: m += f"{video['title']}\n{video['url']}\n"
    else: m += "Sin video nuevo.\n"
    
    # Limitar a 3800 caracteres para Telegram
    if len(m) > 3800:
        print(f"Mensaje demasiado largo ({len(m)} chars), truncando...")
        m = m[:3800]
        last_newline = m.rfind('\n')
        if last_newline > 3500:
            m = m[:last_newline]
    
    return m

def main():
    print("Starting...")
    news = get_market_news()
    crypton = get_crypto_news()
    stocks = [s for s in [get_stock("VWCE.MI", "MSCI World"), get_stock("NVDA", "NVIDIA")] if s]
    indices = [get_index("^GSPC", "S&P 500"), get_index("^IXIC", "NASDAQ"), get_index("^IBEX", "IBEX 35"), get_index("^STOXX", "STOXX 600")]
    cryptos = [c for c in [get_crypto("bitcoin", "BTC"), get_crypto("ethereum", "ETH"), get_crypto("ripple", "XRP")] if c]
    video = get_video()
    msg = make_msg(news, cryptos, stocks, indices, crypton, video)
    send_telegram(msg)
    print("Done!")

if __name__ == "__main__":
    main()
