from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import isodate
import asyncio
from datetime import datetime, timedelta
import logging
import pickle
import os
import json
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()

# Константы из .env
API_KEY = os.getenv("API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE")
TOKEN_FILE = os.getenv("TOKEN_FILE")
CHAT_ID_FILE = "chat_id.txt"
REPORT_DATA_FILE = "report_data.json"
ANALYTICS_CACHE_FILE = "analytics_cache.json"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("youtube_bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальные переменные
youtube = None
youtube_analytics = None
video_ids = []
prev_subscribers = 0
prev_video_views = {}
chat_id = None
last_report_time = None

# Функция для загрузки данных отчета
def load_report_data():
    if os.path.exists(REPORT_DATA_FILE):
        with open(REPORT_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Функция для сохранения данных отчета
def save_report_data(data):
    with open(REPORT_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logger.info(f"Данные отчета сохранены в {REPORT_DATA_FILE}")

# Функция для загрузки кэша аналитики
def load_analytics_cache():
    if os.path.exists(ANALYTICS_CACHE_FILE):
        with open(ANALYTICS_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            cache_time = datetime.fromisoformat(cache.get('timestamp', '1970-01-01'))
            if (datetime.now() - cache_time).total_seconds() < 86400:  # Кэш действителен 24 часа
                return cache.get('data', {})
    return {}

# Функция для сохранения кэша аналитики
def save_analytics_cache(data):
    cache = {
        'timestamp': datetime.now().isoformat(),
        'data': data
    }
    with open(ANALYTICS_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)
    logger.info(f"Кэш аналитики сохранен в {ANALYTICS_CACHE_FILE}")

# Функция для получения учетных данных OAuth
def get_credentials():
    scopes = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/yt-analytics.readonly'
    ]
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
            if credentials.valid:
                return credentials
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(credentials, token)
                return credentials
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, scopes)
    credentials = flow.run_local_server(port=0)
    with open(TOKEN_FILE, 'wb') as token:
        pickle.dump(credentials, token)
    return credentials

# Функция для получения статистики канала (Data API)
def get_channel_stats(youtube, channel_id):
    if youtube is None:
        logger.error("YouTube API не инициализирован в get_channel_stats.")
        return None
    try:
        request = youtube.channels().list(part='statistics', id=channel_id)
        response = request.execute()
        logger.info("Успешно получена статистика канала.")
        return response['items'][0]['statistics']
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            logger.warning("Квота API превышена в get_channel_stats.")
            raise Exception("Quota exceeded")
        logger.error(f"HTTP ошибка при получении статистики канала: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении статистики канала: {e}")
        return None

# Функция для получения всех ID видео с канала
def get_all_video_ids(youtube, channel_id):
    if youtube is None:
        logger.error("YouTube API не инициализирован в get_all_video_ids.")
        return []
    try:
        video_ids = []
        next_page_token = None
        while True:
            request = youtube.search().list(
                part='id',
                channelId=channel_id,
                maxResults=50,
                type='video',
                pageToken=next_page_token
            )
            response = request.execute()
            video_ids.extend([item['id']['videoId'] for item in response['items']])
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        logger.info(f"Успешно получено {len(video_ids)} ID видео.")
        return video_ids
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            logger.warning("Квота API превышена в get_all_video_ids.")
            raise Exception("Quota exceeded")
        logger.error(f"HTTP ошибка при получении ID видео: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении ID видео: {e}")
        return []

# Функция для получения статистики видео (Data API)
def get_video_stats(youtube, video_ids):
    if youtube is None:
        logger.error("YouTube API не инициализирован в get_video_stats.")
        return {}
    try:
        stats = {}
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i:i+50]
            request = youtube.videos().list(
                part='statistics,contentDetails,snippet',
                id=','.join(chunk)
            )
            response = request.execute()
            for item in response['items']:
                duration = isodate.parse_duration(item['contentDetails']['duration']).total_seconds()
                if duration > 320:  # Исключаем Shorts
                    stats[item['id']] = {
                        'viewCount': int(item['statistics'].get('viewCount', 0)),
                        'likeCount': int(item['statistics'].get('likeCount', 0)),
                        'dislikeCount': int(item['statistics'].get('dislikeCount', 0)),
                        'commentCount': int(item['statistics'].get('commentCount', 0)),
                        'title': item['snippet']['title']
                    }
        logger.info(f"Успешно получена статистика для {len(stats)} видео.")
        return stats
    except HttpError as e:
        if e.resp.status == 403 and 'quotaExceeded' in str(e):
            logger.warning("Квота API превышена в get_video_stats.")
            raise Exception("Quota exceeded")
        logger.error(f"HTTP ошибка при получении статистики видео: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка при получении статистики видео: {e}")
        return {}

# Функция для получения аналитики канала за последние 24 часа (Analytics API)
def get_analytics_data(youtube_analytics):
    cache = load_analytics_cache()
    if 'daily_activity' in cache:
        logger.info("Используются кэшированные данные аналитики (daily_activity).")
        return cache['daily_activity']
    
    try:
        today = datetime.now().date()
        yesterday = today - timedelta(days=4)  # Запрос за 4 дня назад для стабильности данных
        request = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=yesterday.strftime('%Y-%m-%d'),
            endDate=yesterday.strftime('%Y-%m-%d'),
            metrics='views,likes,dislikes,comments,shares,estimatedMinutesWatched,averageViewDuration,subscribersGained',
            dimensions='day'
        )
        response = request.execute()
        logger.info(f"Ответ Analytics API (daily_activity): {json.dumps(response, indent=2)}")
        if 'rows' in response and response['rows']:
            row = response['rows'][0]
            data = [
                row[1],  # views
                row[2],  # likes
                row[3],  # dislikes
                row[4],  # comments
                row[5],  # shares
                row[6],  # estimatedMinutesWatched
                row[7],  # averageViewDuration
                row[8]   # subscribersGained
            ]
            cache['daily_activity'] = data
            save_analytics_cache(cache)
            return data
        logger.warning("Нет данных в ответе Analytics API (daily_activity).")
        return [0, 0, 0, 0, 0, 0, 0, 0]
    except HttpError as e:
        logger.error(f"HTTP ошибка при получении аналитики (daily_activity): {e}")
        return [0, 0, 0, 0, 0, 0, 0, 0]
    except Exception as e:
        logger.error(f"Ошибка при получении аналитики (daily_activity): {e}")
        return [0, 0, 0, 0, 0, 0, 0, 0]

# Функция для получения данных о поле аудитории
def get_audience_data(youtube_analytics):
    try:
        today = datetime.now().date()
        last_7_days_start = today - timedelta(days=7)
        request = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=last_7_days_start.strftime('%Y-%m-%d'),
            endDate=today.strftime('%Y-%m-%d'),
            metrics='viewerPercentage',
            dimensions='gender'
        )
        response = request.execute()
        logger.info(f"Ответ Analytics API (audience): {json.dumps(response, indent=2)}")
        
        genders = {'male': 0, 'female': 0}
        for row in response.get('rows', []):
            gender, percentage = row
            genders[gender] = percentage
        
        return genders
    except HttpError as e:
        logger.error(f"HTTP ошибка при получении данных аудитории: {e}")
        return {'male': 0, 'female': 0}
    except Exception as e:
        logger.error(f"Ошибка при получении данных аудитории: {e}")
        return {'male': 0, 'female': 0}

# Функция для получения источников трафика
def get_traffic_sources(youtube_analytics):
    try:
        today = datetime.now().date()
        last_7_days_start = today - timedelta(days=7)
        request = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=last_7_days_start.strftime('%Y-%m-%d'),
            endDate=today.strftime('%Y-%m-%d'),
            metrics='views',
            dimensions='insightTrafficSourceType'
        )
        response = request.execute()
        logger.info(f"Ответ Analytics API (traffic sources): {json.dumps(response, indent=2)}")
        
        traffic = {}
        total_views = sum(row[1] for row in response.get('rows', []))
        for row in response.get('rows', []):
            source, views = row
            traffic[source] = (views / total_views) * 100 if total_views > 0 else 0
        return traffic
    except HttpError as e:
        logger.error(f"HTTP ошибка при получении источников трафика: {e}")
        return {}
    except Exception as e:
        logger.error(f"Ошибка при получении источников трафика: {e}")
        return {}

# Функция для формирования ежедневного отчета
def generate_daily_report(current_stats, video_stats, analytics_data, report_data):
    date = datetime.now().strftime("%d %B %Y")
    report = f"📅 **Ежедневный отчет по каналу**  \nДата: {date}  \n\n"

    # Основные метрики
    subscribers = int(current_stats['subscriberCount'])
    subscriber_diff = subscribers - report_data.get('subscribers', 0)
    total_views = int(current_stats['viewCount'])
    views_diff = total_views - report_data.get('total_views', 0)
    report += "### **Основные метрики**  \n"
    report += f"▫️ **Подписчики:** {subscribers:,} (+{subscriber_diff})  \n"
    report += f"▫️ **Просмотры канала:** {total_views:,} (+{views_diff:,})  \n\n"

    # Активность за 24 часа (из Analytics API)
    views_24h, likes_24h, dislikes_24h, comments_24h, shares_24h, minutes_watched, avg_duration, subs_gained = analytics_data
    report += "### **Активность за 24 часа**  \n"
    if views_24h == 0 and subs_gained == 0:
        report += "⚠️ Данные за последние 24 часа еще не обработаны YouTube Analytics.\n"
    report += f"▫️ **Просмотры:** {views_24h:,}  \n"
    report += f"▫️ **Лайки:** {likes_24h:,}  \n"
    report += f"▫️ **Дизлайки:** {dislikes_24h:,}  \n"
    report += f"▫️ **Комментарии:** {comments_24h:,}  \n"
    report += f"▫️ **Шеры:** {shares_24h:,}  \n"
    report += f"▫️ **Средняя продолжительность просмотра:** {avg_duration:.2f} сек  \n"
    report += f"▫️ **Подписчики за день:** {subs_gained}  \n\n"

    # Топ-видео дня
    video_views_diff = {}
    for video_id, data in video_stats.items():
        prev_data = report_data.get('video_stats', {}).get(video_id, {})
        video_views_diff[video_id] = data['viewCount'] - prev_data.get('viewCount', 0)
    top_videos = sorted(video_views_diff.items(), key=lambda x: x[1], reverse=True)[:2]
    report += "### **Топ-видео дня**  \n"
    for i, (video_id, diff) in enumerate(top_videos, 1):
        video_data = video_stats[video_id]
        report += f"{i}. **«{video_data['title']}»**  \n"
        report += f"   - Просмотры всего: {video_data['viewCount']:,}  \n"
        report += f"   - Лайки: {video_data['likeCount']:,}  \n"
        report += f"   - Дизлайки: {video_data['dislikeCount']:,}  \n"
        report += f"   - Комментарии: {video_data['commentCount']:,}  \n"
        report += "   - % досмотра: N/A (Analytics API)  \n\n"

    # Анализ аудитории (только пол)
    genders = get_audience_data(youtube_analytics)
    report += "### **Анализ аудитории**  \n"
    report += "▫️ **Пол аудитории:**  \n"
    report += f"   - Мужчины: {genders['male']:.1f}%  \n"
    report += f"   - Женщины: {genders['female']:.1f}%  \n"
    report += "▫️ **Процент возвращающихся зрителей:** N/A (Требуется подписка)  \n\n"

    # Источники трафика
    traffic = get_traffic_sources(youtube_analytics)
    report += "### **Источники трафика**  \n"
    report += f"▫️ **Рекомендации YouTube:** {traffic.get('SUGGESTED', 0):.1f}%  \n"
    report += f"▫️ **Поисковые запросы:** {traffic.get('YT_SEARCH', 0):.1f}%  \n"
    report += f"▫️ **Внешние источники:** {traffic.get('EXT_URL', 0):.1f}%  \n\n"

    # Сравнение с прошлыми периодами (заглушка)
    report += "### **Сравнение с прошлыми периодами**  \n"
    report += "▫️ **Подписки:** N/A  \n"
    report += "▫️ **Просмотры:** N/A  \n\n"

    # Общий тренд
    trend = "Подписки и просмотры растут." if subscriber_diff > 0 and views_24h > 0 else "Активность стабильна."
    report += f"📊 **Общий тренд:**  \n{trend}  \n"

    return report

# Фоновая задача
async def background_task():
    global prev_subscribers, prev_video_views, last_report_time
    while True:
        await asyncio.sleep(60)  # Проверка каждые 60 секунд
        if not chat_id:
            logger.warning("Chat ID не установлен, пропуск уведомлений.")
            continue
        try:
            current_stats = get_channel_stats(youtube, CHANNEL_ID)
            current_video_views = get_video_stats(youtube, video_ids)
            analytics_data = get_analytics_data(youtube_analytics)
            report_data = load_report_data()

            # Проверка подписчиков
            if current_stats:
                current_subscribers = int(current_stats['subscriberCount'])
                if current_subscribers > prev_subscribers:
                    diff = current_subscribers - prev_subscribers
                    await bot.send_message(chat_id, f"Подписчиков стало больше на {diff}! Теперь: {current_subscribers}")
                    logger.info(f"Уведомление отправлено: Подписчиков стало больше на {diff}")
                    prev_subscribers = current_subscribers

            # Проверка просмотров видео
            for video_id, data in current_video_views.items():
                if video_id in prev_video_views:
                    current_views = data['viewCount']
                    prev_views = prev_video_views[video_id]['viewCount']
                    if current_views > prev_views:
                        diff = current_views - prev_views
                        await bot.send_message(chat_id, f'Просмотры видео "{data["title"]}" увеличились на {diff}! Теперь: {current_views}')
                        logger.info(f"Уведомление отправлено: Просмотры видео '{data["title"]}' увеличились на {diff}")
                prev_video_views[video_id] = data

            # Отправка ежедневного отчета
            now = datetime.now()
            if last_report_time is None or (now - last_report_time).total_seconds() >= 600:
                report = generate_daily_report(current_stats, current_video_views, analytics_data, report_data)
                await bot.send_message(chat_id, report)
                last_report_time = now
                report_data['subscribers'] = current_subscribers
                report_data['total_views'] = int(current_stats['viewCount'])
                report_data['video_stats'] = {
                    vid: {
                        'viewCount': data['viewCount'],
                        'likeCount': data['likeCount'],
                        'dislikeCount': data['dislikeCount'],
                        'commentCount': data['commentCount']
                    } for vid, data in current_video_views.items()
                }
                save_report_data(report_data)

        except Exception as e:
            if str(e) == "Quota exceeded":
                await bot.send_message(chat_id, "Квота API превышена. Ожидание сброса...")
                logger.warning("Квота API превышена в фоновой задаче.")
                await asyncio.sleep(3600)
            else:
                logger.error(f"Ошибка в фоновой задаче: {e}")
                await bot.send_message(chat_id, f"Ошибка в фоновой задаче: {e}")

# Сохранение chat_id
def save_chat_id():
    if chat_id:
        with open(CHAT_ID_FILE, "w") as f:
            f.write(str(chat_id))

# Обработчик команды /start
@dp.message(Command(commands=['start']))
async def start_command(message: types.Message):
    global chat_id, prev_subscribers, prev_video_views
    chat_id = message.chat.id
    save_chat_id()

    if youtube is None:
        await message.reply("Ошибка: YouTube API не инициализирован.")
        logger.error("Команда /start вызвана, но YouTube API не инициализирован.")
        return

    try:
        stats = get_channel_stats(youtube, CHANNEL_ID)
        if stats:
            subscribers = int(stats['subscriberCount'])
            video_count = int(stats['videoCount'])
            await message.reply(f"Статистика канала:\nПодписчиков: {subscribers}\nЗагруженных видео: {video_count}")
            logger.info(f"Команда /start выполнена: Подписчиков: {subscribers}, Видео: {video_count}")
            prev_subscribers = subscribers
            prev_video_views = get_video_stats(youtube, video_ids)
        else:
            await message.reply("Не удалось получить статистику канала.")
            logger.warning("Не удалось получить статистику канала при выполнении /start.")
    except Exception as e:
        if str(e) == "Quota exceeded":
            await message.reply("Квота API превышена. Попробуйте позже.")
            logger.warning("Квота API превышена при выполнении /start.")
        else:
            await message.reply(f"Ошибка: {e}")
            logger.error(f"Ошибка при выполнении /start: {e}")

# Загрузка chat_id при старте
def load_chat_id():
    global chat_id
    if os.path.exists(CHAT_ID_FILE):
        with open(CHAT_ID_FILE, "r") as f:
            chat_id = f.read().strip()
            if chat_id.isdigit():
                chat_id = int(chat_id)

# Инициализация при запуске
async def on_startup(_):
    global youtube, youtube_analytics, video_ids
    logger.info("Начало инициализации YouTube API с OAuth...")
    load_chat_id()
    try:
        credentials = get_credentials()
        youtube = build('youtube', 'v3', credentials=credentials)
        youtube_analytics = build('youtubeAnalytics', 'v2', credentials=credentials)
        logger.info("YouTube APIs успешно инициализированы.")
    except Exception as e:
        youtube = None
        youtube_analytics = None
        logger.error(f"Ошибка при инициализации YouTube APIs: {e}")
        raise SystemExit(f"Не удалось инициализировать YouTube APIs: {e}")

    logger.info("Получение ID видео с канала...")
    try:
        video_ids = get_all_video_ids(youtube, CHANNEL_ID)
        if not video_ids:
            logger.warning("Не удалось получить ID видео. Возможно, канал пустой или доступ ограничен.")
        else:
            logger.info(f"Успешно получено {len(video_ids)} ID видео.")
            video_stats = get_video_stats(youtube, video_ids)
            logger.info("Список видео на канале:")
            for video_id, data in video_stats.items():
                logger.info(f"ID: {video_id}, Название: {data['title']}")
    except Exception as e:
        video_ids = []
        logger.error(f"Ошибка при получении ID видео в on_startup: {e}")

# Основная функция
async def main():
    logger.info("Запуск бота...")
    await on_startup(None)
    asyncio.create_task(background_task())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())