# YouTube Analytics Telegram Bot

Этот проект представляет собой Telegram-бота, который собирает статистику с YouTube-канала через YouTube Data API и YouTube Analytics API, а затем отправляет ежедневные отчеты в Telegram. Бот предоставляет информацию о подписчиках, просмотрах, топ-видео и других метриках.

## Возможности
- Отслеживание общего числа подписчиков и просмотров канала.
- Ежедневные отчеты с данными за позавчера (из-за задержки Analytics API).
- Уведомления о росте подписчиков и просмотров видео.
- Поддержка кэширования данных для экономии квоты API.
- Логирование всех операций для отладки.

## Требования
- Python 3.8+
- Telegram-аккаунт и токен бота от [BotFather](https://t.me/BotFather).
- Учетные данные Google API (OAuth 2.0) с доступом к YouTube Data API и YouTube Analytics API.

## Установка

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/yourusername/youtube-analytics-bot.git
cd youtube-analytics-bot

python -m venv venv  source venv/bin/activate  # На Windows: venv\Scripts\activate  pip install -r requirements.txt   `

Зависимости (сохраните в requirements.txt):

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   aiogram==3.4.1  google-auth-oauthlib==1.2.0  google-auth-httplib2==0.2.0  google-api-python-client==2.119.0  python-dotenv==1.0.1  isodate==0.6.1   `

3\. Настройте Google API

1.  Перейдите в [Google Cloud Console](https://console.cloud.google.com/).
    
2.  Создайте проект и включите YouTube Data API и YouTube Analytics API.
    
3.  Настройте OAuth 2.0 Client ID (тип "Desktop app").
    
4.  Скачайте файл credentials.json и поместите его в корневую папку проекта.
    

4\. Настройте переменные окруженияСоздайте файл .env в корневой папке проекта и добавьте следующие переменные:

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   API_KEY=your_youtube_api_key  CHANNEL_ID=your_channel_id  # Например, UCxxxxxxxxxxxxxxxxxxxxxx  BOT_TOKEN=your_telegram_bot_token  CREDENTIALS_FILE=credentials.json  TOKEN_FILE=token.pickle   `

*   API\_KEY: API-ключ от Google (не обязателен при использовании OAuth).
    
*   CHANNEL\_ID: ID твоего YouTube-канала (начинается с UC...).
    
*   BOT\_TOKEN: Токен бота от BotFather.
    

5\. Запустите ботаbash

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   python bot.py   `

*   Бот запросит авторизацию через браузер для доступа к YouTube API.
    
*   После авторизации он начнёт отправлять отчеты в Telegram каждые 10 минут (настраивается в коде).
    

Использование

1.  Отправьте команду /start боту в Telegram.
    
2.  Бот ответит текущей статистикой канала и начнёт присылать уведомления и отчеты.
    

Пример отчета

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   📅 Ежедневный отчет по каналу  Дата: 05 марта 2025 (данные за 03 марта 2025)  ### Основные метрики  ▫️ Подписчики: 1,750 (+5)  ▫️ Просмотры канала: 234,344 (+120)  ### Активность за 24 часа  ▫️ Просмотры: 95  ▫️ Лайки: N/A (Data API)  ▫️ Дизлайки: N/A (Data API)  ▫️ Комментарии: N/A (Data API)  ▫️ Шеры: N/A (Analytics API)  ▫️ Средняя продолжительность просмотра: 180.50 сек  ▫️ Подписчики за день: 2  ...   `

Настройка

*   Интервал отчетов: Измените await asyncio.sleep(60) в background\_task на нужное значение (в секундах).
    
*   Логи: Логи сохраняются в youtube\_bot.log для отладки.
    

Известные ограничения

*   YouTube Analytics API обновляет данные с задержкой 24–48 часов, поэтому отчеты показывают данные за позавчера.
    
*   Квота API может быть превышена при частых запросах — используется кэширование для минимизации.
    

ЛицензияЭтот проект распространяется под лицензией MIT. См. файл LICENSE для подробностей.