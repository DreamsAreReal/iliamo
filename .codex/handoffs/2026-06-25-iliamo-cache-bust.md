# Iliamo Cache Bust

## Сделано
- Cache-busting параметр обновлён на `version=20260625-cache-reset-all`.
- `index.html` теперь подключает `styles.min.css`, `app.min.js`, favicon, apple-touch-icon и logo с этим параметром.
- `app.js`/`app.min.js` добавляют этот параметр к динамическим локальным ассетам: logo watermark и фото меню.

## Проверка
- `node --check app.js` и `node --check app.min.js` проходят.
- В Chrome проверены реальные запросы: CSS, JS, logo, favicon и все меню-фото грузятся с `?version=20260625-cache-reset-all`.

## Следующий шаг
- После деплоя открыть сайт обычным refresh; новые URL обойдут старый браузерный кеш.
