# Memory

## 2026-05-18

- Развернут локальный hardened-пайплайн для выжимок стримов LifeChange.
- Скрипты перенесены из root-oriented гайда в проектную папку `scripts/`.
- Добавлена безопасная работа с Groq ключами через переменные окружения или файлы `.secrets/*.key`.
- Добавлена поддержка локального `.env` с `GROQ_API_KEY` и `GROQ_API_KEY_FALLBACK`.
- Реализованы транскрипция с resume-логикой, smoke test, merge частей, генерация `summary_source.md` и валидатор артефактов.
- Исключены лишние Python-зависимости: HTTP multipart к Groq выполняется стандартной библиотекой Python.
- В `meta.json` сохраняется имя исходного файла без абсолютного локального пути.
- Добавлены README, `.gitignore`, структура `input/`, `work/`, `.secrets/` и локальный unittest для merge.
- Добавлен генератор `scripts/build_context_links.py`, который по выжимке и/или `summary_source.md` создаёт короткий текстовый блок `Полезные ссылки из чата` с упомянутыми темами, сервисами и инструментами без URL.
- Добавлен финальный шаг `scripts/build_final_digest.py`: после AI-выжимки он строит блок тем по полной транскрибации и собирает две версии для выгрузки: `summary_outputs/<stem>_summary_with_links.md` и `summary_outputs/<stem>_summary_short_with_links.md`.
- Валидатор `--check-final` теперь требует обе версии с блоком тем и проверяет, что они начинаются с соответствующих исходников `summary.md` и `summary_short.md`.
- Для последней записи `14_maya` созданы `work/14_maya/summary_outputs/14_maya_summary_with_links.md` и `work/14_maya/summary_outputs/14_maya_summary_short_with_links.md`; устаревшие отдельные `context_links.md` и `final.md` удалены из выдачи.
- Создан `CHANGELOG.md` как сжатое System State проекта.
- Добавлен внешний локальный навык `<codex-home>/skills/cash-cleaner` (`Cash_cleaner`) для безопасной dry-run очистки старых артефактов `work` старше 7 дней или адресной очистки по имени.

## 2026-06-04

- Блок `Полезные ссылки из чата` теперь рендерится списком через `•`, а не markdown-буллетами `-`; README и тесты обновлены под новый формат.
- Пайплайн выжимок переведен на дефолт `summary_short.md` + `summary_intermediate.md`; длинная `summary.md` теперь опциональна и готовится только по запросу.
- Добавлен `scripts/build_intermediate_digest.py` для сборки технической промежуточной выжимки: 48 коротких описаний совмещаются с 48 сырыми блоками `summary_source.md`.
- `scripts/build_final_digest.py` больше не требует длинную `summary.md`: короткая версия с блоком тем собирается всегда, длинная `summary_with_links.md` создается только при наличии `summary.md`.
- Из генератора полезных тем удален слабый кандидат `Скрипко и заморозка депозитов`, который срабатывал на любое упоминание слова `депозит`.
