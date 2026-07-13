Что сделано:
- Убраны внешние Google Fonts, сайт использует системные шрифты.
- Добавлены SEO/meta/canonical/favicon/apple-touch-icon.
- Динамические изображения получают loading/decoding/fetchpriority и размеры.
- Новые JPG блюд переведены на оптимизированные WebP и подключены в меню.
- Убран fetch cache no-store для data/menu.json.
- Проверены mobile/desktop smoke-сценарии по всем 13 hash-разделам.

Что не получилось:
- Не удалось получить реальный Lighthouse JSON-отчет: pnpm dlx lighthouse несколько раз падал на fetch/ENOTFOUND registry.npmjs.org, при этом curl к registry периодически отвечал 200.

Следующий шаг:
- Когда npm registry стабильно доступен, запустить Lighthouse mobile и desktop по http://localhost:8000/ и hash-разделам, затем точечно добить оставшиеся audit findings.
