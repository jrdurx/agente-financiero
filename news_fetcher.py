import os
import requests
import json
from datetime import datetime, timezone
import pytz

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
SPAIN_TZ = pytz.timezone('Europe/Madrid')

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=data)

def get_news():
    topics = [
        "economy OR economic OR GDP OR inflation",
        "stock market OR stock markets OR Wall Street",
        "cryptocurrency OR Bitcoin OR Ethereum OR crypto",
        "federal reserve OR interest rates OR monetary policy",
        "trade war OR tariffs OR global trade"
    ]
    
    all_news = []
    for topic in topics:
        url = f"https://newsapi.org/v2/everything?q={topic}&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWSAPI_KEY}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                articles = r.json().get('articles', [])
                all_news.extend(articles)
        except:
            continue
    
    seen = set()
    unique_news = []
    for article in all_news:
        title = article.get('title', '')
        if title and title not in seen and "[Removed]" not in title:
            seen.add(title)
            unique_news.append(article)
    
    return unique_news[:10]

def get_john_economist_video():
    channel_id = "UCZ4Y6Kk2pNuj3fFK8Y4_2_Aw"
    url = f"https://www.googleapis.com/youtube/v3/search?channelId={channel_id}&order=date&maxResults=1&part=snippet&key=AIzaSyDO7Gzk1TQtTpR5LhPmI8a5YcR2zF6mN3w"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('items'):
                video = data['items'][0]['snippet']
                return {
                    'title': video['title'],
                    'url': f"https://www.youtube.com/watch?v={data['items'][0]['id'].get('videoId', '')}",
                    'date': video['publishedAt'][:10]
                }
    except:
        pass
    return None

def format_message(news, video):
    now = datetime.now(SPAIN_TZ).strftime("%d/%m/%Y")
    msg = f"📊 *RESUMEN ECONÓMICO - {now}*\n\n"
    msg += "🔟 *NOTICIAS PRINCIPALES*\n\n"
    
    for i, article in enumerate(news, 1):
        title = article.get('title', 'Sin título')[:100]
        desc = article.get('description', 'Sin descripción')
        if desc:
            desc = desc[:150] + "..." if len(desc) > 150 else desc
        source = article.get('source', {}).get('name', 'Unknown')
        
        msg += f"*{i}. {title}*\n"
        msg += f"   📝 {desc}\n" if desc else ""
        msg += f"   📰 Fuente: {source}\n"
        msg += f"   🎯 Relevancia: Noticia económica relevante\n\n"
    
    if video:
        msg += f"🎬 *ÚLTIMO VIDEO - John Economist*\n"
        msg += f"   📺 {video['title']}\n"
        msg += f"   🔗 {video['url']}\n"
        msg += f"   📅 {video['date']}\n"
    else:
        msg += "🎬 No hay nuevo video de John Economist esta semana.\n"
    
    msg += "\n_Resumen generado automáticamente_"
    return msg

def main():
    news = get_news()
    video = get_john_economist_video()
    message = format_message(news, video)
    send_telegram(message)

if __name__ == "__main__":
    main()
