# max-library

<p align="center">
  <b>Асинхронная Python-библиотека (SDK) для работы с корпоративным мессенджером MAX</b><br>
  <i>(<code>web.oneme.ru</code> / <code>ws-api.oneme.ru</code>)</i>
</p>

<p align="center">
  <a href="https://pypi.org/project/max-library/"><img src="https://img.shields.io/pypi/v/max-library.svg?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/max-library/"><img src="https://img.shields.io/pypi/pyversions/max-library.svg" alt="Python versions"></a>
  <a href="https://github.com/jirnobruh/max-library/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://github.com/jirnobruh/FromMaxToTelegram"><img src="https://img.shields.io/badge/production%20example-FromMaxToTelegram-orange.svg" alt="Production Example"></a>
</p>

---

## ⚡ О библиотеке

`max-library` — это современная, полностью асинхронная клиентская библиотека на Python для взаимодействия с мессенджером **MAX** через WebSocket API.

Библиотека создана для построения надежных сервисов, интеграций и ботов. Она решает классические проблемы блокировок и обрывов соединений благодаря разделению чтения входящих пакетов, RPC-диспетчеризации по sequence ID и автоматическому поддержанию соединения.

### 🌟 Ключевые возможности

- 🚀 **100% AsyncIO:** Построена на базе `websockets` и `aiohttp`, никакого блокирующего ввода-вывода.
- 🔄 **Автоматический Heartbeat и Reconnect:** Встроенный фоновый пинг-понг и прозрачное восстановление WebSocket-сессии при сетевых сбоях.
- ⚡ **Надежная RPC-диспетчеризация:** Запросы сопоставляются с ответами через уникальные `seq`-номера и `asyncio.Future`, исключая коллизии параллельных вызовов.
- 🛡️ **Строгая типизация (Pydantic v2):** Все входящие и исходящие события, сообщения, пользователи, чаты и вложения типизированы и валидируются моделями Pydantic.
- 🎯 **Декларативные фильтры событий:** Удобная система фильтрации входящих сообщений (`filters.text`, `filters.chat_id`, `filters.has_attachments`, поддержка логических операторов `&`, `|`, `~`).
- 📎 **Поддержка файлов и медиа:** Разрешение прямых ссылок на скачивание любых файлов и документов из MAX через внутренний протокол (Opcode 88).
- 💬 **Реакции и ссылки:** Поддержка отправки реакций-эмодзи и парсинг пересланных сообщений / ответов (`FORWARD`, `REPLY`).

---

## 📦 Установка

```bash
pip install max-library
```

---

## 🔑 Получение токена авторизации (MAX_TOKEN)

Для работы с библиотекой требуется авторизационный токен вашей сессии в веб-версии MAX:

1. Откройте веб-клиент мессенджера MAX в браузере ([web.oneme.ru](https://web.oneme.ru)) и авторизуйтесь.
2. Нажмите клавишу **`F12`** (Инструменты разработчика браузера).
3. Перейдите во вкладку **Network** («Сеть») и выберите фильтр **Socket** (или **WS**).
4. Перезагрузите страницу клавишей **`F5`**.
5. Выберите появившееся соединение `websocket`.
6. Перейдите во вкладку **Messages** («Сообщения»).
7. Найдите **3-е сверху** сообщение со стрелкой вверх **`↑ Binary Message`** (исходящий пакет авторизации).
8. В нижнем окне просмотра переключите формат отображения с *Hex Viewer* / *Base64* на **`UTF-8`**.
9. Найдите поле `token` — сразу за ним между двумя служебными знаками-ромбами `` расположен ваш токен:
   ```text
   ...tokenAn_Sx6HQ9HDis041Na5Rpvyb3z8WeP2dnm9......
   ```
10. Скопируйте строку токена (`An_...` без окружающих символов ``) и передайте её в конструктор: `MaxClient(token="...")`.

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

Файлы и документы в MAX приходят с идентификатором `file_id`. Библиотека позволяет получить прямую CDN-ссылку на скачивание:

```python
@client.on_message(filters.has_attachments("FILE"))
async def handle_incoming_file(message):
    for attachment in message.attachments:
        if attachment.file_id:
            # Запрашиваем URL для скачивания через RPC (Opcode 88)
            download_url = await client.get_file_download_url(
                chat_id=message.chat_id,
                message_id=message.id,
                file_id=attachment.file_id
            )
            print(f"Файл {attachment.name}: {download_url}")
```

### Отправка реакций

```python
@client.on_message()
async def add_reaction_to_msg(message):
    # Поставить реакцию ❤️ на сообщение
    await client.add_reaction(
        chat_id=message.chat_id,
        message_id=message.id,
        emoji="❤️"
    )
```

### Получение списка чатов и контактов

```python
async with MaxClient(token="YOUR_TOKEN") as client:
    # Список контактов
    contacts = await client.get_contacts()
    for contact in contacts:
        print(f"Контакт: {contact.name} (ID: {contact.user_id})")

    # Список чатов
    chats = await client.get_chats()
    for chat in chats:
        print(f"Чат: {chat.title} (ID: {chat.id})")
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
