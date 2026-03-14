import os
import sys
import requests
import re
from datetime import datetime
import pytz
import yfinance as yf
import numpy as np
import json
import time

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HF_TOKEN = os.getenv('HF_TOKEN')
SPAIN_TZ = pytz.timezone('Europe/Madrid')

def summarize_with_ai(text):
    if not text or len(text.strip()) < 50:
        return "Sin información disponible."
    
    if not HF_TOKEN:
        print("No HF_TOKEN configured")
        return text[:300] + "..."
    
    try:
        url = "https://router.huggingface.co/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""Eres un experto en análisis financiero. Resume la siguiente noticia en 5-6 frases claras y concisas, capturando los puntos clave:

{text[:2500]}

Resumen:"""

        data = {
            "model": "meta-llama/Llama-3.2-1B-Instruct",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                summary = result['choices'][0]['message']['content'].strip()
                if summary and len(summary) > 20:
                    print(f"AI Summary OK: {len(summary)} chars")
                    return summary
        
        print(f"HF API response: {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"AI error: {e}")
    
    sentences = re.split(r'[.!?]+', text)
    summary_parts = []
    for s in sentences[:4]:
        s = s.strip()
        if s and len(s) > 15:
            summary_parts.append(s)
    
    return ". ".join(summary_parts)[:400] + "..." if summary_parts else text[:300] + "..."

def send_telegram(message):
    try:
        print(f"Message length: {len(message)} chars")
        
        if len(message) > 4000:
            parts = []
            for i in range(0, len(message), 3900):
                parts.append(message[i:i+3900])
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            for idx, part in enumerate(parts):
                r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": part, "parse_mode": "Markdown"}, timeout=15)
                print(f"Telegram part {idx+1}: {r.status_code}")
                if idx < len(parts) - 1:
                    time.sleep(1)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=15)
            print(f"Telegram response: {r.status_code}")
            if r.status_code != 200:
                print(f"Telegram error: {r.text}")
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
                    desc = clean_html(item.findtext('description', ''))
                    full_text = f"Titular: {title}. Descripcion: {desc}" if title else ""
                    
                    if title and title not in seen:
                        seen.add(title)
                        print(f"Processing market news: {title[:40]}...")
                        ai_summary = summarize_with_ai(full_text)
                        news.append({'title': title, 'summary': ai_summary, 'source': 'Yahoo Finance'})
            except Exception as e:
                print(f"Error parsing Yahoo: {e}")
    except Exception as e:
        print(f"Error fetching Yahoo: {e}")
    
    if len(news) < 3:
        try:
            r = requests.get("https://news.google.com/rss/search?q=economia+bolsa&hl=es-ES", timeout=10)
            if r.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.text)
                for item in root.findall('.//item')[:5]:
                    title = item.findtext('title', '')
                    desc = clean_html(item.findtext('description', ''))
                    full_text = f"Titular: {title}. Descripcion: {desc}"
                    
                    if title and title not in seen:
                        seen.add(title)
                        print(f"Processing Google news: {title[:40]}...")
                        ai_summary = summarize_with_ai(full_text)
                        news.append({'title': title, 'summary': ai_summary, 'source': 'Google News'})
        except Exception as e:
            print(f"Error fetching Google: {e}")
    
    return news[:5]

def get_crypto_news():
    news = []
    seen = set()
    try:
        r = requests.get("https://min-api.cryptocompare.com/data/v2/news/?lang=ES", timeout=10)
        if r.status_code == 200:
            for item in r.json().get('Data', [])[:5]:
                title = item.get('title', '')
                body = item.get('body', '')
                full_text = f"Noticia: {title}. Contenido: {body}"
                
                if title and title not in seen:
                    seen.add(title)
                    print(f"Processing crypto news: {title[:40]}...")
                    ai_summary = summarize_with_ai(full_text)
                    source_name = item.get('source_info', {}).get('name', 'Crypto')
                    news.append({'title': title, 'summary': ai_summary, 'source': source_name})
    except Exception as e:
        print(f"Error fetching crypto: {e}")
    
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
        if n.get('summary'):
            m += f"{n['summary']}\n"
        m += f"   ({n['source']})\n\n"
    
    m += "───────────────\n\n📰 *NOTICIAS - CRIPTO*\n\n"
    for i, n in enumerate(crypton, 1):
        m += f"*{i:02d}. {n['title'][:60]}*\n"
        if n.get('summary'):
            m += f"{n['summary']}\n"
        m += f"   ({n['source']})\n\n"
    
    m += "───────────────\n\n📈 *ANALISIS MERCADOS*\n\n"
    for s in stocks:
        m += f"- {s['name']}\n  Precio: {s['price']} | Cambio: {s['change']}% ({s['trend']})\n  RSI: {s['rsi']} - {s['rsi_label']}\n\n"
    
    m += "📊 *INDICES*\n\n"
    for i in indices:
        s = "+" if i['change'] > 0 else ""
        m += f"• {i['name']}: {s}{i['change']}% ({i['trend']})\n"
    m += "\n───────────────\n\n📈 *ANALISIS CRIPTO*\n\n"
    
    for c in cryptos:
        m += f"- {c['name']}: {c['price']}$ ({c['change']}% {c['trend']})\n"
        if c.get('rsi'):
            m += f"  RSI: {c['rsi']} - {c['rsi_label']}\n"
        m += "\n"
    
    m += "───────────────\n\n🧠 *CONCLUSION*\n"
    pos = sum(1 for i in indices if i['change'] > 0)
    m += "Dia positivo en mercados.\n" if pos > 2 else "Dia negativo en mercados.\n" if pos < 2 else "Mercados laterales.\n"
    cpos = sum(1 for c in cryptos if c['change'] > 0)
    m += "Criptos al alza.\n" if cpos > 1 else "Criptos a la baja.\n"
    m += "───────────────\n\n🎬 *JOHN ECONOMIST*\n"
    if video:
        m += f"{video['title']}\n{video['url']}\n"
    else:
        m += "Sin video nuevo.\n"
    
    return m

def main():
    print("=" * 50)
    print("INICIANDO AGENTE FINANCIERO")
    print("=" * 50)
    print(f"TELEGRAM_TOKEN: {'OK' if TELEGRAM_TOKEN else 'FALTA'}")
    print(f"TELEGRAM_CHAT_ID: {'OK' if TELEGRAM_CHAT_ID else 'FALTA'}")
    print(f"HF_TOKEN: {'OK' if HF_TOKEN else 'FALTA'}")
    print("=" * 50)
    
    news = get_market_news()
    print(f"Noticias mercados: {len(news)}")
    
    crypton = get_crypto_news()
    print(f"Noticias crypto: {len(crypton)}")
    
    stocks = [s for s in [get_stock("VWCE.MI", "MSCI World"), get_stock("NVDA", "NVIDIA")] if s]
    indices = [get_index("^GSPC", "S&P 500"), get_index("^IXIC", "NASDAQ"), get_index("^IBEX", "IBEX 35"), get_index("^STOXX", "STOXX 600")]
    cryptos = [c for c in [get_crypto("bitcoin", "BTC"), get_crypto("ethereum", "ETH"), get_crypto("ripple", "XRP")] if c]
    video = get_video()
    
    msg = make_msg(news, cryptos, stocks, indices, crypton, video)
    print(f"Mensaje generado: {len(msg)} caracteres")
    
    send_telegram(msg)
    print("FINALIZADO!")

if __name__ == "__main__":
    main()
