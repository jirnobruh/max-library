# Документация API max-library

`max-library` — асинхронный SDK для взаимодействия с мессенджером MAX по протоколу WebSocket.

---

## Оглавление

1. [Клиент: `MaxClient`](#клиент-maxclient)
   - [Конструктор](#конструктор)
   - [Фабричные методы и хелперы авторизации](#фабричные-методы-и-хелперы-авторизации)
   - [Жизненный цикл](#жизненный-цикл)
   - [Декораторы событий](#декораторы-событий)
   - [Методы API](#методы-api)
2. [Пакет авторизации (`max_library.auth`) и CLI](#пакет-авторизации-max_libraryauth-и-cli)
   - [QR-код авторизация: класс `QRAuthSession`](#qr-код-авторизация-класс-qrauthsession)
   - [Функции модуля `auth`](#функции-модуля-auth)
   - [Консольная утилита CLI (`max-auth`)](#консольная-утилита-cli-max-auth)
3. [Система фильтрации сообщений (`filters`)](#система-фильтрации-сообщений-filters)
4. [Модели данных (Pydantic v2)](#модели-данных-pydantic-v2)
5. [Исключения (`exceptions`)](#исключения-exceptions)
6. [Архитектура транспорта (`MaxTransport`)](#архитектура-транспорта-maxtransport)


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

> **Как получить `token`:**
> 1. **По QR-коду (рекомендуется для серверов/VPS/ПК):** через CLI `python -m max_library auth --qr` или в коде `client = await MaxClient.from_qr()`.
> 2. **Автоматически из браузера (для ПК):** через CLI `python -m max_library auth` или в коде `client = MaxClient.from_browser()`.
> 3. **Вручную:** откройте [web.max.ru](https://web.max.ru) в браузере -> `F12` -> вкладка `Application` -> `Local Storage` -> `https://web.max.ru` -> ключ `__oneme_auth` (значение `An_...`). Либо вкладка `Network` -> `Socket` -> `F5` -> `websocket` -> `Messages` -> 3-е исходящее `↑ Binary Message` (UTF-8).

### Фабричные методы и хелперы авторизации

#### `MaxClient.from_qr(...)`
```python
@classmethod
async def from_qr(
    cls,
    qr_callback: Optional[Callable[[str, str], Union[Awaitable[None], None]]] = None,
    password_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    auto_save_env: bool = False,
    env_file_path: str = ".env",
    var_name: str = "MAX_TOKEN",
    base_ws_url: str = "wss://api.oneme.ru/websocket",
    timeout: float = 120.0,
    **client_kwargs,
) -> MaxClient
```
Интерактивно запускает авторизацию по QR-коду через мобильное приложение MAX, выводит QR-код в консоль (или передает в `qr_callback`), дожидается подтверждения с телефона и возвращает готовый к работе экземпляр `MaxClient`. Если `auto_save_env=True`, автоматически записывает полученный токен в `.env`.

#### `MaxClient.create_qr_session(...)`
```python
@classmethod
async def create_qr_session(
    cls,
    base_ws_url: str = "wss://api.oneme.ru/websocket",
    app_version: str = "26.11.9",
) -> QRAuthSession
```
Создает новую QR-сессию авторизации и возвращает объект `QRAuthSession`. Идеально подходит для сайтов, веб-панелей и ботов, где требуется разделить отдачу QR-кода пользователю (в виде URL, SVG или Data URL) и асинхронное ожидание подтверждения.

#### `MaxClient.login_by_qr(...)`
```python
@classmethod
async def login_by_qr(
    cls,
    qr_callback: Optional[Callable[[str, str], Union[Awaitable[None], None]]] = None,
    password_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    base_ws_url: str = "wss://api.oneme.ru/websocket",
    timeout: float = 120.0,
) -> tuple[str, User]
```
Низкоуровневая авторизация по QR-коду. Возвращает кортеж `(token, user)`.

#### `MaxClient.from_browser(...)`
```python
@classmethod
def from_browser(
    cls,
    browser_name: Optional[str] = None,
    profile_name: Optional[str] = None,
    auto_save_env: bool = False,
    env_file_path: str = ".env",
    var_name: str = "MAX_TOKEN",
    **client_kwargs,
) -> MaxClient
```
Создает экземпляр `MaxClient`, автоматически извлекая токен из локального хранилища браузера (Chrome, Яндекс Браузер, Edge, Opera, Opera GX, Brave, Vivaldi). Если `auto_save_env=True`, автоматически записывает/обновляет переменную в файле `.env`.

#### `MaxClient.get_token_from_browser(...)`
```python
@classmethod
def get_token_from_browser(
    cls,
    browser_name: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> Optional[str]
```
Сканирует хранилища браузеров и возвращает строку токена (`An_...`) либо `None`.

#### `MaxClient.verify_token(token: str, ...)`
```python
@classmethod
async def verify_token(cls, token: str, base_ws_url: str = ...) -> Optional[User]
```
Проверяет токен на сервере MAX (выполняет рукопожатие Opcode 6 и Opcode 19). Возвращает профиль `User` при успехе или `None`, если сессия недействительна.

#### `MaxClient.save_token_to_env(...)`
```python
@classmethod
def save_token_to_env(cls, token: str, env_file_path: str = ".env", var_name: str = "MAX_TOKEN") -> None
```
Безопасно сохраняет или обновляет значение токена в файле `.env`, сохраняя комментарии и структуру файла.

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

## Пакет авторизации (`max_library.auth`) и CLI

Пакет `max_library.auth` отвечает за обнаружение и генерацию токенов авторизации для работы с библиотекой.

Импорт:
```python
from max_library.auth import (
    QRAuthSession,
    create_qr_session,
    login_by_qr,
    generate_qr_svg,
    generate_qr_data_url,
    render_qr_ascii,
    extract_token_from_browser,
    login_by_phone,
    verify_token,
    save_token_to_env,
)
```

---

### QR-код авторизация: класс `QRAuthSession`

Класс для управления активной сессией авторизации по QR-коду. Позволяет веб-приложениям, панелям управления и Telegram-ботам разделять шаг получения данных QR (ссылка, векторный SVG или Data URL) и асинхронное ожидание подтверждения пользователем на смартфоне.

#### Создание сессии (`create_qr_session`):
```python
session = await create_qr_session(base_ws_url="wss://api.oneme.ru/websocket", app_version="26.11.9")
# или через клиент:
session = await MaxClient.create_qr_session()
```

#### Поля экземпляра `QRAuthSession`:
- **`qr_link`**: `str` — Прямой URL авторизации (например, `https://max.ru/:auth/7deea5ff-...`). Этот URL можно передать на фронтенд для рендеринга любым QR-компонентом.
- **`track_id`**: `str` — Уникальный строковый UUID сессии привязки на сервере MAX.
- **`ttl`**: `float` — Время жизни сессии в секундах (по умолчанию 120 с).
- **`polling_interval`**: `float` — Рекомендуемый сервером интервал опроса статуса (по умолчанию 5 с).
- **`expires_at`**: `int | None` — Unix-timestamp в миллисекундах окончания действия QR-кода.

#### Методы `QRAuthSession`:
- **`to_svg(border: int = 2) -> str`**:  
  Возвращает чистую XML-разметку векторного SVG. Не требует сторонних библиотек обработки изображений. Можно напрямую вставлять в HTML-код страницы.
- **`to_data_url(border: int = 2) -> str`**:  
  Возвращает строку вида `data:image/svg+xml;base64,...`, готовую для использования в атрибуте `src` тега `<img>` на сайте: `<img src="{session.to_data_url()}" />`.
- **`to_ascii(border: int = 2) -> str`**:  
  Возвращает высококонтрастное ANSI-представление QR-кода для вывода в консоль (черные блоки на чистом белом фоне).
- **`await wait_for_login(timeout: Optional[float] = None, password_callback=None) -> tuple[str, User]`**:  
  Опрашивает сервер MAX (Opcode 289) до момента сканирования QR-кода пользователем в мобильном приложении MAX. При подтверждении забирает готовый токен (Opcode 291). Если включен 2FA-пароль, запрашивает его через `password_callback` или интерактивно.
- **`await close() -> None`**:  
  Корректно закрывает WebSocket-соединение. Класс также поддерживает контекстный менеджер `async with`.

#### Пример использования в веб-приложении:
```python
async with await MaxClient.create_qr_session() as session:
    # Отдаем ссылку или картинку фронтенду:
    qr_data_url = session.to_data_url()
    
    # Ожидаем сканирования камерой приложения MAX:
    token, user = await session.wait_for_login()
    print(f"Пользователь {user.display_name} вошел! Токен: {token}")
```

---

### Функции модуля `auth`

#### `login_by_qr(...)`
```python
async def login_by_qr(
    qr_callback: Optional[Callable[[str, str], Union[Awaitable[None], None]]] = None,
    password_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    base_ws_url: str = DEFAULT_WS_URL,
    app_version: str = "26.11.9",
    timeout: float = 120.0,
) -> tuple[str, User]
```
Выполняет полный цикл авторизации по QR-коду. Если `qr_callback=None`, выводит высококонтрастный QR-код и инструкцию в терминал. Возвращает кортеж `(token, user)`.

#### `generate_qr_svg(data: str, border: int = 2) -> str`
Генерирует автономную SVG-разметку QR-кода из любой строки или URL.

#### `generate_qr_data_url(data: str, border: int = 2) -> str`
Генерирует Base64 Data URL (`data:image/svg+xml;base64,...`) для отображения в теге `<img>` на сайте.

#### `render_qr_ascii(data: str, border: int = 2) -> str`
Формирует терминальный высококонтрастный QR-код с использованием ANSI-цветов (черный цвет модулей на чистом белом фоне quiet zone) и символов Unicode half-block.

#### `extract_token_from_browser(browser_name=None, profile_name=None) -> Optional[BrowserTokenResult]`
Сканирует файлы хранилища LevelDB (`.ldb`/`.log`) Chromium-браузеров (Chrome, Yandex, Edge, Opera, Opera GX, Brave, Vivaldi) на Windows, macOS и Linux. Возвращает `BrowserTokenResult` с полями `token`, `viewer_id`, `browser`, `profile`, `source_file`.

#### `login_by_phone(phone: str, code_callback=None, ...) -> tuple[str, User]`
Интерактивный вход по номеру телефона через SMS/Push проверочный код (Opcode 17 и 18).

#### `save_token_to_env(token: str, env_file_path=".env", var_name="MAX_TOKEN") -> bool`
Записывает или атомарно обновляет переменную с токеном в `.env`-файле с сохранением комментариев и существующих настроек.

---

### Консольная утилита CLI (`max-auth`)

Библиотека включает встроенный CLI-инструмент для терминала:

```bash
# Запуск через модуль Python:
python -m max_library auth [OPTIONS]

# Либо через консольную команду (после pip install):
max-auth [OPTIONS]
```

#### Доступные параметры:

| Флаг | Описание |
|------|----------|
| `--qr` | Авторизация по QR-коду (сканирование в приложении MAX на смартфоне) |
| `-b, --browser [NAME]` | Поиск токена в браузере (`all`, `yandex`, `chrome`, `edge`, `opera`, `brave`) |
| `-p, --phone PHONE` | Авторизация по номеру телефона (`+79991234567`) |
| `-s, --save [FILE]` | Сохранить полученный токен в `.env` (по умолчанию `.env`) |
| `--var VAR` | Имя переменной для `--save` (по умолчанию `MAX_TOKEN`) |
| `-c, --check` | Проверить полученный токен на сервере MAX API |
| `-q, --quiet` | Вывести только строку токена (для скриптов и `export MAX_TOKEN=$(...)`) |
| `--json` | Вывести результат в структурированном формате JSON |

#### Примеры вызова CLI:
```bash
# Получить токен по QR-коду и сохранить в .env:
python -m max_library auth --qr --save

# Найти токен в Chrome и сохранить в файл config/.env:
python -m max_library auth -b chrome --save config/.env

# Экспортировать токен в переменную окружения Linux/macOS:
export MAX_TOKEN=$(python -m max_library auth --qr -q)
```

---

## 3. Система фильтрации сообщений (`filters`)

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
