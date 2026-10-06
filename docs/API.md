# Документация API max-library

`max-library` — асинхронный SDK для взаимодействия с мессенджером MAX по протоколу WebSocket.

---

## Оглавление

1. [Клиент: `MaxClient`](#клиент-maxclient)
   - [Конструктор](#конструктор)
   - [Жизненный цикл](#жизненный-цикл)
   - [Декораторы событий](#декораторы-событий)
   - [Методы API](#методы-api)
2. [Система фильтрации сообщений (`filters`)](#система-фильтрации-сообщений-filters)
3. [Модели данных (Pydantic v2)](#модели-данных-pydantic-v2)
4. [Исключения (`exceptions`)](#исключения-exceptions)
5. [Архитектура транспорта (`MaxTransport`)](#архитектура-транспорта-maxtransport)

---

## Клиент: `MaxClient`

Основной класс библиотеки, предоставляющий высокоуровневый интерфейс для работы с мессенджером.

Импорт:
```python
from max_library import MaxClient
```

### Конструктор

```python
MaxClient(
    token: str | None = None,
    ws_url: str = "wss://ws-api.oneme.ru/websocket",
    headers: dict | None = None,
    ping_interval: float = 30.0,
    request_timeout: float = 10.0,
    reconnect_attempts: int = 10,
    reconnect_delay: float = 2.0
)
```

- **`token`**: Токен авторизации пользователя MAX (если не передан, можно авторизоваться по номеру телефона и SMS-коду).
- **`ws_url`**: WebSocket endpoint (по умолчанию `wss://ws-api.oneme.ru/websocket`).
- **`headers`**: Дополнительные HTTP-заголовки подключения (Origin по умолчанию `https://web.oneme.ru`).
- **`ping_interval`**: Интервал отправки пинг-пакетов (в секундах).
- **`request_timeout`**: Таймаут ожидания RPC-ответа от сервера на отправленный запрос.
- **`reconnect_attempts`**: Максимальное количество попыток переподключения при разрыве соединения.
- **`reconnect_delay`**: Базовая задержка экспоненциального бэкоффа при реконнекте.

### Жизненный цикл

#### Через контекстный менеджер (рекомендуется):
```python
async with MaxClient(token="YOUR_TOKEN") as client:
    # Сессия автоматически запускается при входе и корректно закрывается при выходе
    await asyncio.Event().wait()
```

#### Ручной запуск и остановка:
```python
client = MaxClient(token="YOUR_TOKEN")
await client.start()
try:
    await asyncio.Event().wait()
finally:
    await client.close()
```

---

### Декораторы событий

#### `@client.on_connect`
Вызывается при успешном подключении и завершении авторизации/инициализации сессии:
```python
@client.on_connect
async def handle_connect():
    print("Соединение установлено!")
```

#### `@client.on_disconnect`
Вызывается при разрыве WebSocket-соединения:
```python
@client.on_disconnect
async def handle_disconnect():
    print("Соединение потеряно, выполняется реконнект...")
```

#### `@client.on_message(filter=None)`
Вызывается при поступлении нового сообщения. Принимает опциональный фильтр:
```python
@client.on_message(filters.text)
async def handle_msg(message: Message):
    print(f"Новый текст: {message.text}")
```

#### `@client.on_event(opcode=None)`
Низкоуровневый перехватчик любых серверных событий (push/responses) по их Opcode:
```python
@client.on_event(128)  # Opcode 128: входящее сообщение
async def handle_raw_event(event: IncomingEvent):
    print(f"Сырые данные: {event.payload}")
```

---

### Методы API

#### Отправка сообщений: `send_message`
```python
async def send_message(
    chat_id: int | str,
    text: str,
    reply_to_message_id: int | str | None = None
) -> Message
```
Отправляет текстовое сообщение в указанный чат (Opcode 64). Поддерживает ответ на сообщение по ID.

#### Скачивание файлов: `get_file_download_url`
```python
async def get_file_download_url(
    chat_id: int | str,
    message_id: int | str,
    file_id: int | str,
    item_type: str = "REGULAR"
) -> str
```
Запрашивает через RPC (Opcode 88) прямую ссылку на скачивание файла из облака MAX. Возвращает валидный URL (например, `https://...`).

#### Реакции: `add_reaction` / `remove_reaction`
```python
async def add_reaction(chat_id: int | str, message_id: int | str, emoji: str) -> None
async def remove_reaction(chat_id: int | str, message_id: int | str, emoji: str) -> None
```
Устанавливает или удаляет реакцию (эмодзи) на указанном сообщении.

#### Контакты и чаты: `get_contacts` / `get_chats`
```python
async def get_contacts() -> list[Contact]
async def get_chats() -> list[Chat]
```
Возвращает список сохранённых контактов или чатов текущего аккаунта.

#### История чата: `get_chat_history`
```python
async def get_chat_history(chat_id: int | str, limit: int = 50, offset: int = 0) -> list[Message]
```
Получает список последних сообщений в чате.

#### Профиль пользователя: `get_profile`
```python
async def get_profile(user_id: int | str) -> User
```
Возвращает информацию о пользователе (имя, телефон, никнейм, статус).

---

## Система фильтрации сообщений (`filters`)

Библиотека предоставляет декларативную систему фильтров, аналогичную современным фреймворкам для ботов:

```python
from max_library import filters
```

### Доступные фильтры:
- `filters.all`: Пропускает абсолютно все сообщения.
- `filters.text`: Только сообщения, содержащие непустой текст.
- `filters.chat_id(123)` или `filters.chat_id([123, 456])`: Сообщения только из указанного чата / чатов.
- `filters.sender_id(789)`: Сообщения только от определенного отправителя.
- `filters.has_attachments(attachment_type)`: Наличие вложений определенного типа (`"PHOTO"`, `"FILE"`, `"VIDEO"`, `"LINK"` и др.).
- `filters.command("start")`: Проверка команды в начале текста сообщения (например, `/start`).

### Комбинирование операторами:
- **`&` (AND)**: `filters.text & filters.chat_id(12345)`
- **`|` (OR)**: `filters.has_attachments("PHOTO") | filters.has_attachments("FILE")`
- **`~` (NOT)**: `~filters.command("help")`

---

## Модели данных (Pydantic v2)

Все входящие и исходящие структуры используют строгую валидацию на базе `pydantic.BaseModel` с включенным автоматическим приведением типов:

```python
from max_library.models import (
    Message,
    Attachment,
    MessageLink,
    User,
    Contact,
    Chat,
    Reactions,
    IncomingEvent
)
```

### Поля модели `Message`:
- `id`: `int | str` — Уникальный ID сообщения.
- `chat_id`: `int | str | None` — ID чата, к которому относится сообщение.
- `text`: `str | None` — Текст сообщения.
- `sender`: `User | None` — Объект отправителя.
- `time`: `int | None` — Время отправки (timestamp в миллисекундах).
- `attachments`: `list[Attachment]` — Список прикрепленных файлов/медиа.
- `link`: `MessageLink | None` — Пересланное сообщение (`FORWARD`) или ответ (`REPLY`).
- `reactions`: `Reactions | None` — Реакции под сообщением.

### Поля модели `Attachment`:
- `type`: `str` — Тип вложения (`"PHOTO"`, `"FILE"`, `"VIDEO"`, `"LINK"`).
- `name`: `str | None` — Название файла.
- `size`: `int | None` — Размер в байтах.
- `file_id`: `int | str | None` — Идентификатор файла в системе MAX.
- `token`: `str | None` — Токен доступа к вложению.
- `photo_token`: `str | None` — Токен фотографии.
- `base_url`: `str | None` — Базовый URL (если доступен).

---

## Исключения (`exceptions`)

- `MaxClientError`: Базовое исключение для всех ошибок библиотеки.
- `MaxAPIError`: Ошибка, возвращенная сервером MAX в ответ на запрос (содержит `code` и `message`).
- `MaxTimeoutError`: Истекло время ожидания ответа от сервера на RPC-запрос.
- `VerifyCodeWrong`: Неверный код подтверждения при авторизации по SMS.
- `TransportClosedError`: Попытка отправки сообщения при закрытом WebSocket-соединении.

---

## Архитектура транспорта (`MaxTransport`)

Внутреннее взаимодействие с WebSocket-сервером организовано по высоконадежной схеме:

```text
               +---------------------------+
               |   WebSocket ws-api.oneme  |
               +-------------+-------------+
                             |
                      [_read_loop()]
                             |
             +---------------+---------------+
             |                               |
       [Пакет с seq]                   [Server Push]
             |                               |
  _pending_requests[seq]              _push_queue
             |                               |
    Future.set_result()              @on_message /
                                     @on_event
```

- **Один фоновый reader**: Исключает коллизии параллельных вызовов `recv()`.
- **RPC по `seq`**: Генератор `seq` создает запрос и помещает `asyncio.Future` в словарь ожидающих ответов `_pending_requests`. Читающий цикл по прибытию ответа с этим же `seq` мгновенно пробуждает ожидающий вызов без задержек и гонок данных.
- **Очередь Pushes**: Входящие события и уведомления от других пользователей направляются в очередь `_push_queue` для асинхронной обработки подписчиками.
