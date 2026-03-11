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
                    'source': item.get('source_info', {}).get('name', 'CryptoCompare'),
                    'url': item.get('url', ''),
                    ' relevance': 'Criptomonedas'
                })
            return news
    except:
        pass
    return []

def get_market_news():
    all_news = []
    
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search?q=market%20OR%20stocks%20OR%20economy&quotesCount=0&newsCount=5"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json().get('news', [])
            for item in data:
                all_news.append({
                    'title': item.get('title', ''),
                    'description': item.get('summary', '')[:200],
                    'source': 'Yahoo Finance',
                    'url': item.get('link', ''),
                    'relevance': 'Mercados'
                })
    except:
        pass
    
    try:
        url = "https://newsdata.io/api/1/news?apikey=pub_demo&q=reserva%20federal%20OR%20fed%20OR%20tipos%20de%20inter%C3%A9s&language=es"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            for item in r.json().get('results', [])[:3]:
                all_news.append({
                    'title': item.get('title', ''),
                    'description': item.get('description', '')[:200],
                    'source': item.get('source_id', 'Noticias'),
                    'url': item.get('link', ''),
                    'relevance': 'Macro'
                })
    except:
        pass
    
    return all_news[:10]

def get_john_economist_video():
    url = "https://www.youtube.com/results?search_query=John+Economist&sp=CAI%253D"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            import re
            data = r.text
            match = re.search(r'"videoId":"([^"]+)","title":"([^"]+)","length', data)
            if match:
                video_id = match.group(1)
                title = match.group(2).replace('\\u0026', '&')
                return {
                    'title': title,
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'date': datetime.now(SPAIN_TZ).strftime("%Y-%m-%d")
                }
    except:
        pass
    return None

def get_all_news():
    news = []
    seen = set()
    
    yahoo = get_yahoo_news()
    for item in yahoo:
        title = item.get('title', '')[:80]
        if title and title not in seen:
            seen.add(title)
            news.append({
                'title': title,
                'description': item.get('description', '')[:200],
                'source': item.get('source_id', 'Fuente'),
                'relevance': 'Economía'
            })
    
    market = get_market_news()
    for item in market:
        title = item.get('title', '')[:80]
        if title and title not in seen:
            seen.add(title)
            news.append(item)
    
    crypto = get_coinnews()
    for item in crypto:
        title = item.get('title', '')[:80]
        if title and title not in seen:
            seen.add(title)
            news.append(item)
    
    return news[:10]

def format_message(news, video):
    now = datetime.now(SPAIN_TZ).strftime("%d/%m/%Y")
    msg = f"📊 *RESUMEN ECONÓMICO - {now}*\n\n"
    msg += "🔟 *NOTICIAS PRINCIPALES*\n\n"
    
    for i, article in enumerate(news, 1):
        title = article.get('title', 'Sin título')[:100]
        desc = article.get('description', 'Sin descripción')
        source = article.get('source', 'Unknown')
        relevance = article.get('relevance', 'Noticia económica')
        
        msg += f"*{i}. {title}*\n"
        msg += f"   📝 {desc}\n" if desc else ""
        msg += f"   📰 Fuente: {source}\n"
        msg += f"   🎯 Relevancia: {relevance}\n\n"
    
    if video:
        msg += f"🎬 *ÚLTIMO VIDEO - John Economist*\n"
        msg += f"   📺 {video['title']}\n"
        msg += f"   🔗 {video['url']}\n"
        msg += f"   📅 {video['date']}\n"
    else:
        msg += "🎬 No hay nuevo video de John Economist.\n"
    
    msg += "\n_Resumen generado automáticamente_"
    return msg

def main():
    news = get_all_news()
    video = get_john_economist_video()
    message = format_message(news, video)
    send_telegram(message)

if __name__ == "__main__":
    main()
