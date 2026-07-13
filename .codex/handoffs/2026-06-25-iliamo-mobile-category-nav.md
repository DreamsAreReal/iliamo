# Iliamo Mobile Category Nav

## Сделано
- Мобильная навигация категорий переведена в сетку 3 колонки.
- Все 13 категорий видны сразу без горизонтального скролла.
- На мобиле отображаются полные названия категорий с переносом в 2 строки.
- Последняя одиночная категория `Соусы` центрируется в средней колонке.
- Обновлены `app.js`, `app.min.js`, `styles.css`, `styles.min.css` и inline critical CSS в `index.html`.
- Cache-bust версия обновлена на `20260625-category-fullnames-centered`.

## Проверка
- Chrome mobile 320px: 13/13 категорий видны, rowCount 5, horizontal overflow false, text overflow false.
- Chrome mobile 390px: 13/13 категорий видны, rowCount 5, horizontal overflow false, text overflow false; `Соусы` grid-column 2.

## Следующий шаг
- После деплоя сделать hard reload на телефоне, чтобы проверить поведение sticky nav в реальном браузере.
