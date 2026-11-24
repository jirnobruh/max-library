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
    phone: str | None = None,
    base_ws_url: str = "wss://api.oneme.ru/websocket",
    auto_reconnect: bool = True,
    num_workers: int = 4,
    app_version: str = "26.11.9",
    device_id: str | None = None,
    heartbeat_interval: float = 45.0,
    heartbeat_timeout: float = 120.0,
)
```

- **`token`**: Токен авторизации веб-сессии MAX (`An_...`).
- **`phone`**: Номер телефона (для авторизации по SMS через `auth()`).
- **`base_ws_url`**: WebSocket endpoint (по умолчанию `wss://api.oneme.ru/websocket`).
- **`auto_reconnect`**: Автоматическое переподключение при обрыве соединения (по умолчанию `True`).
- **`num_workers`**: Количество параллельных воркеров для обработки входящих событий (по умолчанию `4`).
- **`app_version`**: Версия клиента в заголовках и рукопожатии (по умолчанию `26.11.9`).
- **`device_id`**: Уникальный идентификатор устройства (UUID).
- **`heartbeat_interval`**: Интервал отправки пинг-пакетов (по умолчанию `45.0` с).
- **`heartbeat_timeout`**: Таймаут ожидания понга перед переподключением (по умолчанию `120.0` с).

> **Как получить `token`:** Откройте веб-клиент MAX ([web.max.ru](https://web.max.ru)) в браузере -> `F12` -> вкладка `Network` -> фильтр `Socket` -> `F5` -> выберите `websocket` -> вкладка `Messages` -> 3-е сверху `↑ Binary Message` -> режим `UTF-8` -> скопируйте значение после слова `token` между служебными знаками (например, `An_...`).

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

#### `@client.on_message(filters=None)`
Вызывается при поступлении нового сообщения. Принимает опциональный фильтр:
```python
@client.on_message(filters.text)
async def handle_msg(message: Message):
    print(f"Новый текст: {message.text}")
```

---

### Методы API

#### Отправка сообщений: `send_message`
```python
async def send_message(
    chat_id: int | str,
    text: str = "",
    reply_id: str | int | None = None,
    notify: bool = True,
    cid: int | None = None,
    attaches: Optional[list[Union[Attachment, dict[str, Any]]]] = None,
) -> Message
```
Отправляет текстовое сообщение и/или вложения в указанный чат (Opcode 64). Поддерживает ответ на сообщение по ID (`reply_id`).

#### Редактирование сообщения: `edit_message`
```python
async def edit_message(
    chat_id: int | str,
    message_id: str | int,
    text: str,
) -> Message
```
Изменяет текст существующего отправленного сообщения (Opcode 67).

#### Удаление сообщений: `delete_message`
```python
async def delete_message(
    chat_id: int | str,
    message_ids: Union[Sequence[str | int], str, int],
    for_me: bool = False,
) -> None
```
Удаляет одно или несколько сообщений в чате для всех или только для себя (Opcode 66).

#### История чата: `get_history`
```python
async def get_history(
    chat_id: int | str,
    backward: int = 30,
    forward: int = 0,
    from_time: int | None = None,
) -> list[Message]
```
Получает список сообщений чата (Opcode 49) с пагинацией назад (`backward`) и вперед (`forward`) от указанного времени `from_time` (timestamp в миллисекундах).

#### Скачивание файлов: `get_file_download_url`
```python
async def get_file_download_url(
    chat_id: int | str,
    message_id: int | str,
    file_id: int | str,
    item_type: str = "REGULAR",
) -> str | None
```
Запрашивает через RPC (Opcode 88) прямую CDN-ссылку на скачивание файла из облака MAX (`https://fd.oneme.ru/getfile?...`).

#### Скачивание видео: `get_video_download_url`
```python
async def get_video_download_url(
    chat_id: int | str,
    message_id: int | str,
    video_id: int | str,
    token: str | None = None,
    item_type: str = "REGULAR",
) -> str | None
```
Запрашивает через RPC (Opcode 83) прямую ссылку на видеопоток/скачивание видео (поддерживает резолв MP4 в разных разрешениях).

#### Реакции: `set_reaction`
```python
async def set_reaction(
    chat_id: int | str,
    message_id: str | int,
    reaction: str,
) -> Reactions
```
Устанавливает эмодзи-реакцию на указанное сообщение (Opcode 178).

#### Пользователи: `get_user`
```python
async def get_user(
    id: int | str | None = None,
    phone: str | None = None,
    chat_id: int | None = None,
) -> User
```
Получает профиль пользователя по ID контакта (Opcode 32), номеру телефона (Opcode 46) или interlocutor ID в личном диалоге (`chat_id`).

#### Управление контактами
```python
async def contact_add(user_id: int | str) -> User
async def contact_remove(user_id: int | str) -> bool
async def contact_block(user_id: int | str) -> bool
async def contact_unblock(user_id: int | str) -> bool
```
Добавление, удаление, блокировка и разблокировка контактов (Opcode 34).

#### Чаты: `get_chats`, `get_chat`, `pin_chat`, `unpin_chat`
```python
async def get_chats(count: int = 40, force_refresh: bool = False) -> list[Chat]
async def get_chat(chat_id: int | str, force_refresh: bool = False) -> Chat
async def pin_chat(chat_id: int | str) -> bool
async def unpin_chat(chat_id: int | str) -> bool
```
Получение списка чатов (Opcode 19), информации о чате по ID (Opcode 48), закрепление и открепление чата (Opcode 22).

#### Завершение сессии: `session_exit`
```python
async def session_exit() -> bool
```
Отзывает активный токен сессии на сервере (Opcode 20) и закрывает соединение.

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

### Поля и методы модели `Attachment`:
- `type`: `str` — Тип вложения (`"PHOTO"`, `"FILE"`, `"VIDEO"`, `"AUDIO"`, `"STICKER"`, `"LINK"`).
- `name`: `str | None` — Название файла.
- `size`: `int | None` — Размер в байтах.
- `file_id`: `int | str | None` — Идентификатор файла в системе MAX (для Opcode 88).
- `video_id`: `int | str | None` — Идентификатор видеофайла в системе MAX (для Opcode 83).
- `audio_id`: `int | str | None` — Идентификатор аудиофайла.
- `mime_type`: `str | None` — MIME-тип содержимого.
- `token`: `str | None` — Токен доступа к медиа.
- `photo_token`: `str | None` — Токен фотографии.
- `base_url` / `base_raw_url` / `preview_url`: `str | None` — Доступные базовые URL.
- Свойства:
  - `url`: `str | None` — Возвращает наилучший доступный прямой URL из метаданных.
  - `is_photo`: `bool` — Является ли вложение фотографией.
  - `is_video`: `bool` — Является ли вложение видео.
  - `is_file`: `bool` — Является ли вложение документом/файлом.
- Асинхронные методы:
  - `await get_download_url(message=None, client=None) -> str | None`: Автоматически запрашивает ссылку на скачивание (для документов — через Opcode 88, для видео — через Opcode 83) или возвращает готовый прямой URL.

### Поля и методы модели `Chat`:
- `id`: `int | str` — Уникальный идентификатор чата.
- `title`: `str | None` — Название чата.
- `display_name`: `str` — Человекочитаемое имя (название чата, имя собеседника в диалоге или fallback `"Чат <id>"`).
- `type`: `str | None` — Тип (`"DIALOG"`, `"CHAT"`, `"CHANNEL"`).
- `description`: `str | None` — Описание чата.
- `link`: `str | None` — Ссылка-приглашение.
- `participants_count`: `int | None` — Число участников.
- `base_icon_url`: `str | None` — Ссылка на аватар чата.
- Асинхронные методы:
  - `await pin() -> bool`: Закрепить чат в списке.
  - `await unpin() -> bool`: Открепить чат.
  - `await send_message(text, **kwargs) -> Message`: Отправить сообщение в этот чат.

---

## Исключения (`exceptions`)

- `MaxClientError`: Базовое исключение для всех ошибок библиотеки.
- `MaxAPIError`: Ошибка, возвращенная сервером MAX в ответ на запрос (содержит `code`, `title` и `message`).
- `MaxConnectionError`: Ошибка сетевого соединения при работе с WebSocket.
- `MaxTimeoutError`: Истекло время ожидания ответа от сервера на RPC-запрос.
- `AuthError`: Ошибка аутентификации пользователя или инвалидный токен.
- `VerifyCodeWrong`: Неверный код подтверждения при авторизации по SMS.
- `UserNotFoundError`: Пользователь не найден по ID или номеру телефона.
- `ChatNotFoundError`: Чат не найден по ID.
- `TransportClosedError`: Попытка отправки запроса при закрытом WebSocket-соединении.

---

## Архитектура транспорта (`MaxTransport`)

Внутреннее взаимодействие с WebSocket-сервером организовано по высоконадежной асинхронной схеме поверх бинарного протокола **MsgPack v10**:

```text
               +-----------------------------------+
               |  WebSocket wss://api.oneme.ru     |
               +-----------------+-----------------+
                                 |
                          [_read_loop()]
                                 |
                 +---------------+---------------+
                 |                               |
           [Пакет с seq]                   [Server Push]
                 |                               |
      _pending_requests[seq]                _push_queue
                 |                               |
        Future.set_result()              @client.on_message
```

- **MsgPack v10 Framed Protocol**: Сообщения кодируются в компактный бинарный формат с заголовком длины и opcode пакета.
- **Один фоновый reader**: Исключает коллизии параллельных вызовов чтения сокета.
- **RPC по `seq`**: Генератор `seq` создает запрос и помещает `asyncio.Future` в словарь ожидающих ответов `_pending_requests`. Читающий цикл по прибытию ответа с этим же `seq` мгновенно пробуждает ожидающий вызов без задержек и гонок данных.
- **Очередь Pushes**: Входящие события и уведомления от других пользователей направляются в очередь `_push_queue` для параллельной обработки пулом воркеров.
