# MAX Client Library (`max-client`)

Асинхронная Python-библиотека (SDK) для взаимодействия с корпоративным мессенджером MAX (`web.oneme.ru` / `ws-api.oneme.ru`).

## Особенности
- Полностью асинхронная архитектура на базе `asyncio`, `websockets` и `aiohttp`.
- Строгая типизация и валидация входящих/исходящих событий через `pydantic v2`.
- Управление WebSocket-сессией: автоматический heartbeat (ping/pong), обработка отключений и reconnect.
- Модули для авторизации, получения контактов/чатов, приёма входящих сообщений, отправки текста, медиа и реакций.

## Установка

В режиме разработки:
```bash
pip install -e .
```

## Быстрый старт
```python
import asyncio
from max_library import MaxClient

async def main():
    async with MaxClient(token="YOUR_MAX_TOKEN") as client:
        # Регистрация обработчиков событий и запуск клиента
        pass

if __name__ == "__main__":
    asyncio.run(main())
```
