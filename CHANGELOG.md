# System State — Выжимки стримов LifeChange

_Последнее обновление: 2026-06-20_

## Переменные и константы

- `DEFAULT_BLOCK_SECONDS` (`int = 240`, `scripts/merge_groq_parts.py`) — длительность одного блока `summary_source.md` в секундах; количество блоков = `ceil(duration / block_seconds)`.
- `DEFAULT_CHUNK_SECONDS` (`int = 300`, `scripts/groq_transcribe.py`) — длительность аудиочанка для отправки в Groq; переопределяется через `--chunk-seconds` или `GROQ_CHUNK_SECONDS`.
- `MAX_CHUNK_SECONDS` (`int = 900`, `scripts/groq_transcribe.py`) — максимально допустимый размер чанка.
- `MAX_RETRIES` (`int = 6`, `scripts/groq_transcribe.py`) — попыток на один чанк перед ошибкой.
- `DEFAULT_MODEL` (`str = "whisper-large-v3-turbo"`, `scripts/groq_transcribe.py`) — модель транскрибации Groq; переопределяется через `--model` или `GROQ_TRANSCRIBE_MODEL`.
- `DEFAULT_LANGUAGE` (`str = "ru"`, `scripts/groq_transcribe.py`) — язык транскрибации; переопределяется через `--language` или `GROQ_LANGUAGE`.
- `DEFAULT_PRICE_PER_HOUR` (`float = 0.04`, `scripts/groq_transcribe.py`) — цена Groq за час аудио в USD.
- `API_URL` (`str`, `scripts/groq_transcribe.py`) — `"https://api.groq.com/openai/v1/audio/transcriptions"`, зашит в код.
- `DOMAIN_RE` (`re.Pattern`, `scripts/build_context_links.py`) — `r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s)\],;]*)?"`; ищет домены в тексте.
- `LINK_CANDIDATES` (`list[LinkCandidate]`, `scripts/build_context_links.py`) — словарь тем для блока `Полезные ссылки из чата`:
  `Рыбный день`, `Про безопасность активов`, `Про гифты в Telegram`, `Arkham аналитика предикшнов`,
  `Собираем роли в Discord`, `Уязвимость для VPS`, `Умные очки`, `Google перевод`,
  `Hyperliquid Spot`, `Polymarket и Kalshi`, `Notion MCP`, `Playwright и Selenium`, `Trezor и SafePal`.
- `TARGET_BLOCKS` (`int`, `scripts/build_intermediate_digest.py`) — **удалена**; количество блоков теперь читается динамически из `summary_source.md`.
- `DEFAULT_WORK_DIR` (`Path`, внешний навык `cash-cleaner`) — `<project-root>/work`.

## Функции и модули

- `scripts/groq_transcribe.py::main()` — точка входа; режет аудио на чанки, транскрибирует через Groq, resume от последнего `end` в `segments.json`, атомарно пишет артефакты.
- `scripts/groq_transcribe.py::load_dotenv(path: Path) -> None` — парсит `.env`, не перезаписывает уже установленные env-переменные.
- `scripts/groq_transcribe.py::load_api_keys(args) -> list[str]` — собирает уникальный список ключей из `--api-key-file`, `--fallback-api-key-file`, `GROQ_API_KEY`, `GROQ_API_KEY_FALLBACK`.
- `scripts/groq_transcribe.py::make_chunk(source, chunk_path, start, duration) -> None` — ffmpeg: opus 32k / 16kHz / моно, без shell-интерпретации.
- `scripts/groq_transcribe.py::transcribe_chunk(api_keys, chunk_path, model, language, retries) -> dict` — цикл по ключам + retry с экспоненциальным backoff и учётом `Retry-After`.
- `scripts/groq_transcribe.py::normalize_segments(raw, offset) -> list[dict]` — приводит ответ Groq к `[{start, end, text}]` со сдвигом `offset`.
- `scripts/groq_transcribe.py::write_transcript(path, segments) -> None` — пишет `.txt` с таймкодом каждые 30 с.
- `scripts/groq_transcribe.py::atomic_write_text(path, content) -> None` — запись через tmp + rename.
- `scripts/groq_transcribe.py::reject_path_like_stem(stem: str) -> str` — запрещает `/`, `\`, `\x00`, `.`, `..`.
- `scripts/merge_groq_parts.py::write_summary_source(path, segments, total_duration, block_seconds) -> int` — делит длительность на `ceil(total_duration / block_seconds)` равных окон, в каждое собирает текст сегментов; возвращает фактическое количество строк.
- `scripts/merge_groq_parts.py::load_part(out_dir, part) -> tuple[list, dict]` — загружает `<part>_segments.json` + `<part>_meta.json`, валидирует поля.
- `scripts/merge_groq_parts.py::write_transcript(path, segments) -> None` — таймкод каждые 30 с.
- `scripts/merge_groq_parts.py::reject_path_like_stem(stem) -> str` — защита от path-traversal.
- `scripts/build_intermediate_digest.py::read_blocks(path, kind, expected=None) -> list[str]` — читает непустые строки файла, проверяет формат `HH:MM:SS`, опционально сверяет count с `expected`.
- `scripts/build_intermediate_digest.py::build_intermediate_digest(work_dir, stem, labels=None) -> Path` — читает `summary_source.md` (N строк), читает label-файл (N строк), совмещает в `summary_intermediate.md`.
- `scripts/build_intermediate_digest.py::pick_label_path(summary_dir, stem, explicit) -> Path` — приоритет: explicit → `_summary_intermediate_notes.md` → `_summary.md`.
- `scripts/build_context_links.py::build_links(summary_text, limit) -> list[str]` — матчит `LINK_CANDIDATES` по ключевым словам, затем домены из `DOMAIN_RE`; возвращает не более `limit` строк.
- `scripts/build_context_links.py::render_link_block(links) -> str` — рендерит `## Полезные ссылки из чата:` списком через `•` без URL.
- `scripts/build_final_digest.py::build_final_digest(work_dir, stem, limit) -> list[Path]` — всегда пишет `_summary_short_with_links.md`; пишет `_summary_with_links.md` только если существует `_summary.md`.
- `scripts/validate_outputs.py::main()` — базовая проверка groq-артефактов; `--check-final` дополнительно проверяет summary-файлы; количество блоков берёт из `meta["summary_source_lines"]`.
- `scripts/smoke_test.py` — 30-секундный тест Groq API перед длинным прогоном.
- `.claude/skills/summarize.md` — агентский скилл Claude Code: автоопределяет stem, генерирует `summary_intermediate_notes.md` и `summary_short.md`, запускает build-скрипты и валидацию.

## Архитектурные решения

- Нет Python-зависимостей кроме stdlib; HTTP multipart к Groq собирается вручную через `urllib`.
- Groq API ключи только через `.env` / `.secrets/*.key`; не логируются, не попадают в README.
- Количество блоков `summary_source.md` динамическое: `ceil(duration / block_seconds)`, дефолт 4 мин/блок. Фиксированные 48 строк убраны.
- `summary_source_lines` сохраняется в `meta.json` и является единственным источником правды для валидатора и `build_intermediate_digest`.
- Агентская выжимка (`summary_short.md`, `summary_intermediate_notes.md`) выполняется Claude Code через скилл — без отдельного API-вызова.
- Автотриггер через `CLAUDE.md` в корне проекта: любая просьба «выжимку / summary / сводку» → скилл `summarize` без явного `/summarize`.
- Все записи артефактов атомарны (tmp + rename).
- `ffmpeg`/`ffprobe` вызываются без shell-интерпретации.
- Очистка `work/` вынесена во внешний навык `cash-cleaner`.

## Структуры данных / схемы

- `groq_outputs/<part>_segments.json`: `[{start: float, end: float, text: str}, ...]`
- `groq_outputs/<part>_meta.json`: `{provider, transcription_model, language, source_file, audio_duration_seconds, chunk_seconds, segment_count, cost_usd}`
- `groq_outputs/<stem>_segments.json`: объединённые сегменты со сдвигом offset по частям
- `groq_outputs/<stem>_transcript.txt`: строки `HH:MM:SS  текст` (два пробела), таймкод каждые 30 с
- `groq_outputs/<stem>_summary_source.md`: N строк `HH:MM:SS  текст блока` (два пробела), N = `summary_source_lines`
- `groq_outputs/<stem>_meta.json`: `{provider, parts, audio_duration_seconds, segment_count, cost_usd, summary_source_lines}`
- `summary_outputs/<stem>_summary_intermediate_notes.md`: N строк `HH:MM:SS  Короткое описание` — входной label-файл для `build_intermediate_digest`; генерирует скилл
- `summary_outputs/<stem>_summary_intermediate.md`: `# Промежуточная выжимка` + N блоков `## HH:MM:SS Описание\n\nсырой текст`
- `summary_outputs/<stem>_summary_short.md`: 19–24 строки, ≤ 4000 символов, формат `HH:MM:SS Глагол конкретика` (один пробел), без точки в конце строк, «мы» не «автор»
- `summary_outputs/<stem>_summary.md`: опционально, N строк, формат `HH:MM:SS  Глагол конкретика` (два пробела)
- `summary_outputs/<stem>_summary_short_with_links.md`: `summary_short.md` + `\n\n## Полезные ссылки из чата:\n\n• ...`
- `summary_outputs/<stem>_summary_with_links.md`: `summary.md` + блок тем; создаётся только при наличии `summary.md`

## Конфиги и переменные окружения

- `.env` — исключён из git; `GROQ_API_KEY`, `GROQ_API_KEY_FALLBACK`, опционально `GROQ_TRANSCRIBE_MODEL`, `GROQ_LANGUAGE`, `GROQ_CHUNK_SECONDS`, `GROQ_PRICE_PER_HOUR`.
- `.secrets/groq_primary.key` — основной Groq ключ, исключён из git.
- `.secrets/groq_fallback.key` — fallback Groq ключ, исключён из git.
- `CLAUDE.md` (корень проекта) — автотриггер скилла summarize для Claude Code.
- `.claude/skills/summarize.md` — скилл агентской выжимки.

## Внешние интеграции

- Groq API: `https://api.groq.com/openai/v1/audio/transcriptions`, модель `whisper-large-v3-turbo`.
- Системные утилиты: `ffmpeg`, `ffprobe` (нарезка и измерение длительности аудио).
- Внешний навык: `<codex-home>/skills/cash-cleaner` (очистка `work/`).

## Текущие задачи (TODO / In Progress)

- [x] Динамические блоки `summary_source.md` вместо фиксированных 48.
- [x] Скилл `summarize` для Claude Code с автотриггером через `CLAUDE.md`.
- [x] Создан `CHANGELOG.md` как System State проекта.

## Открытые вопросы

- Нужно ли встроить очистку `work/` как проектный скрипт в `scripts/` вместо внешнего `cash-cleaner`.

## История изменений

### 2026-06-20

- Убран `TARGET_LINES = 48`; добавлен `DEFAULT_BLOCK_SECONDS = 240`; количество блоков = `ceil(duration / block_seconds)`; `--block-seconds` в `merge_groq_parts.py`.
- `write_summary_source` теперь принимает `block_seconds: int` и возвращает `int` (фактический счётчик блоков).
- `summary_source_lines` сохраняется в `meta.json`; валидатор и `build_intermediate_digest` читают значение из meta вместо хардкода.
- `read_blocks` в `build_intermediate_digest.py` сделана динамической: `expected` опционален, блок-счётчик берётся из длины `summary_source.md`.
- Создан `.claude/skills/summarize.md` — агентский скилл генерации выжимки внутри Claude Code без API.
- Создан `CLAUDE.md` в корне проекта с автотриггером скилла при любой просьбе «сделать выжимку».
- Тесты обновлены под динамический счётчик; все 4 теста проходят.

### 2026-06-11

- Строки `summary_short.md` больше не должны заканчиваться точкой; валидатор, тесты и README синхронизированы.

### 2026-06-04

- Блок `Полезные ссылки из чата` переведён на `•` вместо markdown `-`.
- Пайплайн переведён на дефолт `summary_short.md` + `summary_intermediate.md`; `summary.md` стала опциональной.
- Добавлен `scripts/build_intermediate_digest.py`.
- `build_final_digest.py` больше не требует `summary.md`; `summary_short_with_links.md` собирается всегда.
- Удалён слабый кандидат `Скрипко и заморозка депозитов` из `LINK_CANDIDATES`.

### 2026-05-18

- Развёрнут локальный hardened-пайплайн; скрипты перенесены в `scripts/`.
- Безопасная работа с ключами через `.env` и `.secrets/*.key`.
- Реализованы транскрибация с resume-логикой, smoke test, merge частей, генерация `summary_source.md`, валидатор артефактов.
- Добавлен `scripts/build_context_links.py` (темы/домены без URL).
- Добавлен `scripts/build_final_digest.py` (два финальных файла с блоком тем).
- Добавлен внешний навык `cash-cleaner` для очистки `work/`.
