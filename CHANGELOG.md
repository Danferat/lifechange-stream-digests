# System State — Выжимки стримов LifeChange

_Последнее обновление: 2026-05-18 12:20 MSK_

## Переменные и константы

- `TARGET_LINES` (`int`, `scripts/merge_groq_parts.py`) — количество строк в `summary_source.md`; текущее значение `48`.
- `DOMAIN_RE` (`re.Pattern`, `scripts/build_context_links.py`) — регулярное выражение для поиска явных доменов в тексте.
- `LINK_CANDIDATES` (`list[LinkCandidate]`, `scripts/build_context_links.py`) — словарь тем для блока `Полезные ссылки из чата`; содержит темы `Рыбный день`, `Про безопасность активов`, `Про гифты в Telegram`, `Arkham аналитика предикшнов`, `Собираем роли в Discord`, `Уязвимость для VPS`, `Умные очки`, `Google перевод`, `Hyperliquid Spot`, `Polymarket и Kalshi`, `Notion MCP`, `Playwright и Selenium`, `Trezor и SafePal`, `Скрипко и заморозка депозитов`.
- `DEFAULT_WORK_DIR` (`Path`, внешний навык `<codex-home>/skills/cash-cleaner/scripts/clean_work_cache.py`) — папка очистки по умолчанию `<user-home>/Desktop/Вайбкодинг/выжимки стримов/work`.

## Функции и модули

- `scripts/groq_transcribe.py` — транскрибирует один аудиофайл через Groq Whisper с resume-логикой, чанками, atomic write и безопасным чтением ключей из `.env` или `.secrets/*.key`.
- `scripts/smoke_test.py` — выполняет короткую проверку Groq API перед длинным прогоном.
- `scripts/merge_groq_parts.py::reject_path_like_stem(stem: str) -> str` — запрещает path-like stem для выходных имён.
- `scripts/merge_groq_parts.py::fmt_ts(seconds: float) -> str` — форматирует секунды в `HH:MM:SS`.
- `scripts/merge_groq_parts.py::atomic_write_text(path: Path, content: str) -> None` — атомарно записывает текстовые артефакты.
- `scripts/merge_groq_parts.py::atomic_write_json(path: Path, value: Any) -> None` — атомарно записывает JSON.
- `scripts/merge_groq_parts.py::load_part(out_dir: Path, part: str) -> tuple[list[dict[str, Any]], dict[str, Any]]` — загружает `<part>_segments.json` и `<part>_meta.json`, валидирует обязательные поля.
- `scripts/merge_groq_parts.py::write_transcript(path: Path, segments: list[dict[str, Any]]) -> None` — пишет склеенную транскрибацию с таймкодом примерно каждые 30 секунд.
- `scripts/merge_groq_parts.py::write_summary_source(path: Path, segments: list[dict[str, Any]], total_duration: float) -> None` — пишет `summary_source.md` из 48 равных временных блоков.
- `scripts/build_context_links.py::normalize_text(text: str) -> str` — нормализует текст для поиска ключевых слов.
- `scripts/build_context_links.py::candidate_matches(candidate: LinkCandidate, normalized: str) -> bool` — проверяет совпадение темы по ключевым словам.
- `scripts/build_context_links.py::build_links(summary_text: str, limit: int) -> list[str]` — строит список тем/доменов для блока `Полезные ссылки из чата`, без URL.
- `scripts/build_context_links.py::render_link_block(links: list[str]) -> str` — рендерит markdown-блок `## Полезные ссылки из чата:` обычным списком.
- `scripts/build_final_digest.py::build_final_digest(work_dir: Path, stem: str, limit: int) -> tuple[Path, Path]` — создаёт две версии для выгрузки: `<stem>_summary_with_links.md` и `<stem>_summary_short_with_links.md`.
- `scripts/validate_outputs.py::main() -> None` — проверяет обязательные groq-артефакты; с `--check-final` проверяет `summary.md`, `summary_short.md`, `summary_with_links.md`, `summary_short_with_links.md`.
- `<codex-home>/skills/cash-cleaner/scripts/clean_work_cache.py::validate_target(target: Path) -> Path` — разрешает очистку только директории с именем `work`.
- `<codex-home>/skills/cash-cleaner/scripts/clean_work_cache.py::find_candidates(target: Path, days: int, names: list[str]) -> tuple[list[Candidate], list[str]]` — ищет immediate children внутри `work`, старше `--days` или выбранные через `--name`.
- `<codex-home>/skills/cash-cleaner/scripts/clean_work_cache.py::remove_path(path: Path) -> None` — удаляет файл или директорию-кандидат; вызывается только при `--apply`.

## Архитектурные решения

- Проект остаётся локальным Python-пайплайном без Python-зависимостей для основных скриптов.
- Groq API ключи не передаются через README/логи; используются `.env`, `.secrets/groq_primary.key`, `.secrets/groq_fallback.key`.
- Транскрибация и merge сохраняют промежуточные артефакты инкрементально и атомарно.
- `summary.md` и `summary_short.md` создаются LLM-агентом по `summary_source.md`.
- Блок `Полезные ссылки из чата` строится локально по полной транскрибации, без веб-поиска и без URL.
- Финальная выдача состоит из двух файлов: обычная выжимка + блок тем и короткая выжимка + тот же блок тем.
- Устаревшие отдельные `context_links.md` и `final.md` больше не являются актуальным контрактом выдачи.
- Очистка кэша вынесена во внешний навык `cash-cleaner`, чтобы не затрагивать функционал проекта.

## Структуры данных / схемы

- `groq_outputs/<part>_segments.json`: список объектов с полями `start`, `end`, `text`.
- `groq_outputs/<part>_meta.json`: объект с обязательным `audio_duration_seconds`; может содержать `cost_usd`.
- `groq_outputs/<stem>_segments.json`: объединённые сегменты с учётом offset частей.
- `groq_outputs/<stem>_transcript.txt`: транскрибация с таймкодами.
- `groq_outputs/<stem>_summary_source.md`: 48 строк формата `HH:MM:SS  текст блока`.
- `groq_outputs/<stem>_meta.json`: `provider`, `parts`, `audio_duration_seconds`, `segment_count`, `cost_usd`, `summary_source_lines`.
- `summary_outputs/<stem>_summary.md`: ровно 48 строк, формат `HH:MM:SS  Глагол конкретика`, два пробела после таймкода.
- `summary_outputs/<stem>_summary_short.md`: 19-24 строки, не больше 4000 символов, один пробел после таймкода, точка в конце каждой строки.
- `summary_outputs/<stem>_summary_with_links.md`: начинается с содержимого `<stem>_summary.md`, затем содержит блок `Полезные ссылки из чата`.
- `summary_outputs/<stem>_summary_short_with_links.md`: начинается с содержимого `<stem>_summary_short.md`, затем содержит блок `Полезные ссылки из чата`.

## Конфиги и переменные окружения

- `.env` — локальный файл, исключён из git; поддерживает `GROQ_API_KEY` и `GROQ_API_KEY_FALLBACK`.
- `.secrets/groq_primary.key` — локальный основной Groq ключ, исключён из git.
- `.secrets/groq_fallback.key` — локальный fallback Groq ключ, исключён из git.

## Внешние интеграции

- Groq audio transcriptions API.
- Модель транскрибации: `whisper-large-v3-turbo`.
- Внешние утилиты: `ffmpeg`, `ffprobe`.
- Telegram-конфиги/боты в проекте не зафиксированы.

## Текущие задачи (TODO / In Progress)

- [x] Добавлен генератор блока `Полезные ссылки из чата` без URL.
- [x] Добавлена сборка двух итоговых версий с блоком тем: обычной и короткой.
- [x] Добавлен внешний навык `cash-cleaner` для безопасной очистки старых артефактов в `work`.
- [x] Создано сжимание контекста в `CHANGELOG.md`.

## Открытые вопросы

- Нужно ли встроить очистку `work` как проектный скрипт в `scripts/` и README, или достаточно внешнего навыка `cash-cleaner`.
- Нужно ли удалять старые элементы `work` по `mtime` директории или по дате внутри имени/метаданных записи.

## История изменений

### 2026-05-18

- Развёрнут локальный hardened-пайплайн для выжимок стримов LifeChange.
- Добавлена безопасная работа с Groq ключами через `.env` и `.secrets/*.key`.
- Реализованы транскрибация с resume-логикой, smoke test, merge частей, генерация `summary_source.md` и валидатор артефактов.
- Добавлен `scripts/build_context_links.py` для локального поиска тем/сервисов/доменов в тексте и рендера блока `Полезные ссылки из чата` без URL.
- Добавлен `scripts/build_final_digest.py`, создающий `<stem>_summary_with_links.md` и `<stem>_summary_short_with_links.md`.
- Обновлён `scripts/validate_outputs.py`: `--check-final` требует обе версии с блоком тем и проверяет их начало против исходных `summary.md` / `summary_short.md`.
- Для записи `14_maya` созданы `14_maya_summary_with_links.md` и `14_maya_summary_short_with_links.md`.
- Устаревшие `14_maya_context_links.md` и `14_maya_final.md` удалены из выдачи.
- Добавлен внешний навык `<codex-home>/skills/cash-cleaner` с dry-run очисткой `work` старше 7 дней и адресной очисткой по `--name`.
