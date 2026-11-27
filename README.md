# max-library

<p align="center">
  <b>Асинхронная Python-библиотека (SDK) для работы с корпоративным мессенджером MAX</b><br>
  <i>(<code>web.max.ru</code> / <code>api.oneme.ru/websocket</code>)</i>
</p>

<p align="center">
  <a href="https://pypi.org/project/max-library/"><img src="https://img.shields.io/pypi/v/max-library.svg?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/max-library/"><img src="https://img.shields.io/pypi/pyversions/max-library.svg" alt="Python versions"></a>
  <a href="https://github.com/jirnobruh/max-library/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://github.com/jirnobruh/FromMaxToTelegram"><img src="https://img.shields.io/badge/production%20example-FromMaxToTelegram-orange.svg" alt="Production Example"></a>
</p>

---

## ⚡ О библиотеке

`max-library` — это современная, полностью асинхронная клиентская библиотека на Python для взаимодействия с мессенджером **MAX** через WebSocket API по бинарному протоколу MsgPack v10.

Библиотека создана для построения надежных сервисов, интеграций и ботов. Она решает классические проблемы блокировок и обрывов соединений благодаря разделению чтения входящих пакетов, RPC-диспетчеризации по sequence ID и автоматическому поддержанию соединения.

### 🌟 Ключевые возможности

- 🚀 **100% AsyncIO:** Построена на базе `websockets` и `aiohttp`, никакого блокирующего ввода-вывода.
- 🔄 **Автоматический Heartbeat и Reconnect:** Встроенный фоновый пинг-понг и прозрачное восстановление WebSocket-сессии при сетевых сбоях.
- ⚡ **Надежная RPC-диспетчеризация:** Запросы сопоставляются с ответами через уникальные `seq`-номера и `asyncio.Future`, исключая коллизии параллельных вызовов.
- 🛡️ **Строгая типизация (Pydantic v2):** Все входящие и исходящие события, сообщения, пользователи, чаты и вложения типизированы и валидируются моделями Pydantic.
- 🎯 **Декларативные фильтры событий:** Удобная система фильтрации входящих сообщений (`filters.text`, `filters.chat_id`, `filters.has_attachments`, поддержка логических операторов `&`, `|`, `~`).
- 📎 **Поддержка файлов и медиа:** Разрешение прямых ссылок на скачивание любых файлов и документов (Opcode 88) и видео (Opcode 83) через внутренний протокол MAX.
- 💬 **Реакции и ссылки:** Поддержка установки реакций-эмодзи и парсинг пересланных сообщений / ответов (`FORWARD`, `REPLY`).

---

## 📦 Установка

```bash
pip install max-library
```

---

## 🔑 Получение токена авторизации (MAX_TOKEN)

Для работы с библиотекой требуется авторизационный токен вашей сессии в веб-версии MAX (`An_...`). Получить его можно несколькими удобными способами:

---

### Способ 1: Авторизация по QR-коду (Универсально: ПК, VPS, Серверы) 🔥

Самый удобный способ без ввода номеров телефонов, капчи (VK Captcha) и СМС. Подходит как для локального компьютера, так и для **удаленных серверов (VPS / Docker)** по SSH.

1. Запустите в терминале команду:
   ```bash
   python -m max_library auth --qr --save
   ```
2. В консоли появится высококонтрастный QR-код.
3. Откройте мобильное приложение **MAX** на смартфоне:
   * **Настройки** → **Устройства** → **Привязать устройство**
   * Наведите камеру телефона на QR-код в терминале.
4. Консоль мгновенно зафиксирует подтверждение, отобразит профиль и сохранит `MAX_TOKEN=An_...` в файл `.env`.

#### В коде Python:

```python
from max_library import MaxClient

# Авторизоваться по QR-коду и получить готового клиента:
client = await MaxClient.from_qr(auto_save_env=True)
print(f"Авторизован как: {client.me.display_name}")
```

---

### Способ 2: Сканирование локального браузера (Для ПК)

Если вы уже вошли в [web.max.ru](https://web.max.ru) в любом браузере на вашем компьютере (Chrome, Яндекс Браузер, Edge, Opera, Opera GX, Brave, Vivaldi), библиотека умеет автоматически извлекать активный токен из локального хранилища:

#### В терминале (CLI):

```bash
# 1. Быстро найти токен и проверить его валидность через MAX API
python -m max_library auth

# 2. Найти токен и сразу автоматически сохранить/обновить его в .env:
python -m max_library auth --save

# 3. Вывести только строку токена (удобно для скриптов: export MAX_TOKEN=$(...)):
python -m max_library auth --quiet

# 4. Вывести подробную информацию в формате JSON:
python -m max_library auth --json
```

#### В коде Python:

```python
from max_library import MaxClient

# Создать клиента с токеном из браузера в одну строчку
client = MaxClient.from_browser(auto_save_env=True)

# Или просто получить строку токена
token = MaxClient.get_token_from_browser()
```

---

### Способ 3: Вручную через DevTools браузера 

Если вы хотите достать токен вручную:

1. Откройте веб-клиент мессенджера MAX в браузере ([web.max.ru](https://web.max.ru)) и авторизуйтесь.
2. Нажмите клавишу **`F12`** (Инструменты разработчика браузера).
3. **Вариант через Local Storage (самый быстрый):**
   * Перейдите во вкладку **Application** («Приложение») -> слева выберите **Storage** -> **Local Storage** -> `https://web.max.ru`.
   * Найдите ключ **`__oneme_auth`** — в его значении скопируйте строку токена (`An_...`).
4. **Вариант через WebSocket Network:**
   * Перейдите во вкладку **Network** («Сеть») и выберите фильтр **Socket** (или **WS**).
   * Перезагрузите страницу клавишей **`F5`**.
   * Выберите появившееся соединение `websocket` -> вкладка **Messages** («Сообщения»).
   * Найдите **3-е сверху** сообщение со стрелкой вверх **`↑ Binary Message`** (исходящий пакет авторизации).
   * В нижнем окне просмотра переключите формат с *Hex Viewer* на **`UTF-8`**.
   * Скопируйте строку токена (`An_...`) сразу за полем `token`.
5. Передайте полученный токен в конструктор: `MaxClient(token="...")` или сохраните в переменную окружения `MAX_TOKEN`.

---

## 🚀 Быстрый старт

### 1. Простой эхо-бот

```python
import asyncio
from max_library import MaxClient, filters
from max_library.models import Message

client = MaxClient(token="ВАШ_MAX_TOKEN")

@client.on_connect
async def handle_connect():
    print("Успешное подключение к мессенджеру MAX!")

# Обработчик только текстовых сообщений
@client.on_message(filters.text)
async def handle_text_message(message: Message):
    print(f"Получено сообщение от {message.sender.name}: {message.text}")
    
    if message.text == "/ping":
        await client.send_message(
            chat_id=message.chat_id,
            text="pong!"
        )

async def main():
    async with client:
        # Держим процесс активным
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 💡 Примеры использования

### Фильтрация сообщений

Вы можете комбинировать фильтры логическими операторами (`&` - И, `|` - ИЛИ, `~` - НЕ):

```python
from max_library import MaxClient, filters

client = MaxClient(token="YOUR_TOKEN")

# Ловим только сообщения с картинками в конкретном чате
photo_in_target_chat = filters.chat_id(123456789) & filters.has_attachments("PHOTO")

@client.on_message(photo_in_target_chat)
async def handle_photo(message):
    print(f"Фотография получена в целевом чате! Вложений: {len(message.attachments)}")

# Ловим сообщения с файлами или ссылками
files_or_links = filters.has_attachments("FILE") | filters.has_attachments("LINK")

@client.on_message(files_or_links)
async def handle_files(message):
    print("Получен файл или ссылка")
```

### Получение прямой ссылки на скачивание файла
 
Файлы и документы в MAX приходят с идентификатором `file_id`, а видео — с `video_id`. Библиотека позволяет получить прямую CDN-ссылку на скачивание:
 
```python
@client.on_message(filters.has_attachments("FILE") | filters.has_attachments("VIDEO"))
async def handle_incoming_file(message):
    for attachment in message.attachments:
        # Способ 1: через удобный метод вложения
        download_url = await attachment.get_download_url(message, client=client)
        if download_url:
            print(f"Файл {attachment.name}: {download_url}")

        # Способ 2: напрямую через RPC клиента
        if attachment.file_id:
            url = await client.get_file_download_url(
                chat_id=message.chat_id,
                message_id=message.id,
                file_id=attachment.file_id
            )
            print(f"Прямая ссылка: {url}")
```

### Установка реакций

```python
@client.on_message()
async def add_reaction_to_msg(message):
    # Поставить реакцию ❤️ на сообщение (Opcode 178)
    await client.set_reaction(
        chat_id=message.chat_id,
        message_id=message.id,
        reaction="❤️"
    )
```

### Получение списка чатов и профиля пользователя

```python
async with MaxClient(token="YOUR_TOKEN") as client:
    # Информация о пользователе по ID или номеру телефона
    user = await client.get_user(id=12345678)
    print(f"Пользователь: {user.display_name} (ID: {user.id})")

    # Список чатов (с кэшированием)
    chats = await client.get_chats()
    for chat in chats:
        print(f"Чат: {chat.display_name} (ID: {chat.id})")
```

---

## 📖 Документация API

Подробное описание архитектуры, методов `MaxClient`, моделей данных Pydantic и кодов исключений доступно в [документации API](docs/API.md).

---

## 🛠️ Пример в Production

Библиотека `max-library` лежит в основе высоконадежного бота пересылки:
👉 **[FromMaxToTelegram](https://github.com/jirnobruh/FromMaxToTelegram)** — асинхронный Telegram-бот, пересылающий текст, медиагруппы (альбомы) и файлы из чатов MAX в Telegram-форумы и каналы с умным кэшем пользователей и ротацией логов.

---

## 🤝 Разработка и тестирование

Клонирование репозитория и запуск тестов:

```bash
git clone https://github.com/jirnobruh/max-library.git
cd max-library
python -m venv .venv
# Активируйте виртуальное окружение
pip install -e ".[dev]"
pytest
```

---

## 📄 Лицензия

Проект распространяется под лицензией [MIT](LICENSE).
Автор: **[jirnobruh](https://github.com/jirnobruh)**.
