# Выжимки стримов LifeChange

Локальный пайплайн для транскрипции `.ogg`-стримов через Groq Whisper и подготовки исходника для итоговой выжимки.

## Что делает проект

1. Режет один аудиофайл на короткие чанки.
2. Отправляет чанки в Groq `whisper-large-v3-turbo`.
3. Инкрементально сохраняет сегменты, чтобы можно было продолжить после сбоя.
4. Склеивает одну или несколько частей стрима.
5. Создаёт `summary_source.md` из N равных временных блоков по 4 минуты.
6. LLM-агент готовит короткую выжимку, техническую промежуточную выжимку и список реально
   упомянутых в стриме инструментов/сервисов (`summary_mentioned_materials.md`).
7. Блок `Полезные ссылки из чата` собирается из этого списка; если агент его не подготовил,
   скрипт как фолбэк ищет по полной транскрибации совпадения из фиксированного словаря тем.
8. Собирает короткую версию для выгрузки с блоком полезных тем.
9. Собирает длинную версию только если вручную подготовлен `<stem>_summary.md`.
10. Проверяет готовые артефакты перед сдачей.

Для АМА есть отдельный режим: после скринов вопросов он строит кандидаты по речевым сегментам, подтверждает начала чтения вопросов и создаёт список таймкодов плюс `ama_source.md`, разбитый по вопросам.

`summary_short.md` и `summary_intermediate.md` собираются LLM-агентом по `summary_source.md`. После этого локальный скрипт добавляет блок тем по транскрибации и создаёт короткую версию для выгрузки. Длинная `summary.md` собирается только по отдельному запросу; если она есть, скрипт дополнительно создаёт длинную версию с блоком тем.

## Технологии

- Язык: Python 3
- Внешние утилиты: `ffmpeg`, `ffprobe`, `yt-dlp` (только для стримов по ссылке на YouTube)
- Внешний API: Groq audio transcriptions
- Модель: `whisper-large-v3-turbo`
- База данных: не используется
- Python-зависимости: не требуются, используется стандартная библиотека
- Основные папки: `input/`, `work/`, `scripts/`, `.secrets/`

## Безопасность

- Не вставляйте Groq ключи в команды, README, GUIDE или логи.
- Кладите ключи в `.env` или в `.secrets/groq_primary.key` и `.secrets/groq_fallback.key`.
- Файл `.env` исключён из git.
- Папка `.secrets/` исключена из git.
- Скрипты не логируют значения ключей.
- Сетевой адрес Groq API зафиксирован в коде и не берётся из пользовательского ввода.
- Все файловые записи артефактов выполняются атомарно.
- Вызовы `ffmpeg` и `ffprobe` выполняются без shell-интерпретации аргументов.

Если ключи из старого `GUIDE.md` были настоящими, их нужно перевыпустить.

## Подготовка

Проверьте, что установлены:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

Создайте `.env` в корне проекта:

```bash
cp .env.example .env
```

Откройте `.env` и вставьте два ключа:

```text
GROQ_API_KEY=gsk_...
GROQ_API_KEY_FALLBACK=gsk_...
```

Альтернативно можно использовать файлы `.secrets/groq_primary.key` и `.secrets/groq_fallback.key`.

Положите аудио в `input/`.

### Если источник - ссылка на YouTube, а не локальный файл

Установите `yt-dlp` (один раз):

```bash
brew install yt-dlp ffmpeg
```

Скачайте аудиодорожку сразу в рабочую папку стрима:

```bash
mkdir -p work/<stem>/groq_outputs work/<stem>/summary_outputs
yt-dlp --no-playlist -f "bestaudio" -x --audio-format mp3 --audio-quality 5 \
  -o "work/<stem>/source.%(ext)s" "https://www.youtube.com/watch?v=..."
```

Дальше файл `work/<stem>/source.mp3` обрабатывается как обычный локальный источник - см. ниже.

Если `yt-dlp` выдаёт `HTTP Error 403` или "Only images are available for download", версия устарела:

```bash
brew upgrade yt-dlp
```

## Пробный запуск

Сначала короткий smoke test:

```bash
python3 scripts/smoke_test.py "input/stream.ogg" \
  --api-key-file .secrets/groq_primary.key
```

Если ключи лежат в `.env`, параметр `--api-key-file` не нужен:

```bash
python3 scripts/smoke_test.py "input/stream.ogg"
```

Если smoke test вернул `SMOKE_OK`, можно запускать транскрипцию:

```bash
mkdir -p work/stream/groq_outputs work/stream/summary_outputs

python3 scripts/groq_transcribe.py "input/stream.ogg" "work/stream/groq_outputs" part1
```

Затем слияние одной части:

```bash
python3 scripts/merge_groq_parts.py "work/stream" stream part1
```

Для двух частей:

```bash
python3 scripts/groq_transcribe.py "input/part1.ogg" "work/stream/groq_outputs" part1 \
  --api-key-file .secrets/groq_primary.key \
  --fallback-api-key-file .secrets/groq_fallback.key

python3 scripts/groq_transcribe.py "input/part2.ogg" "work/stream/groq_outputs" part2 \
  --api-key-file .secrets/groq_fallback.key \
  --fallback-api-key-file .secrets/groq_primary.key

python3 scripts/merge_groq_parts.py "work/stream" stream part1 part2
```

## Проверка

После merge:

```bash
python3 scripts/validate_outputs.py "work/stream" stream
```

После ручной сборки `summary_intermediate.md` и `summary_short.md`:

```bash
python3 scripts/build_intermediate_digest.py "work/stream" stream

python3 scripts/build_final_digest.py "work/stream" stream --limit 12

python3 scripts/validate_outputs.py "work/stream" stream --check-final
```

### АМА-таймкоды

Обычная выжимка и АМА-таймкоды - разные режимы. АМА не использует четырёхминутные блоки: границы определяются началом чтения каждого вопроса.

После транскрипции подготовьте файл с вопросами, по одному на строку, например `work/ama/summary_outputs/ama_ama_questions.md`. Скрипт сначала выдаёт кандидаты, затем после ручной проверки - финальные файлы:

```bash
python3 scripts/build_ama_timecodes.py "work/ama" ama \
  "work/ama/summary_outputs/ama_ama_questions.md"

python3 scripts/build_ama_timecodes.py "work/ama" ama \
  "work/ama/summary_outputs/ama_ama_questions.md" \
  --review-file "work/ama/summary_outputs/ama_ama_timecodes_review.md"

python3 scripts/validate_outputs.py "work/ama" ama --check-ama
```

Итог: `summary_outputs/ama_ama_timecodes.md` и `groq_outputs/ama_ama_source.md`.

## Полезные ссылки из чата

Основной источник блока - `summary_outputs/<stem>_summary_mentioned_materials.md`. Это
список реальных инструментов/сервисов/проектов, которые LLM-агент выписал из `summary_source.md`
именно для этого стрима (по одной строке `• Название`). `build_final_digest.py` подставляет
этот список в блок `Полезные ссылки из чата` как есть.

Если файл `summary_mentioned_materials.md` отсутствует (старые стримы, обработанные до
появления этого шага), скрипт использует фолбэк - автоматический поиск по фиксированному
словарю тем и доменов в полной транскрибации:

```bash
python3 scripts/build_context_links.py \
  "work/stream/summary_outputs/stream_summary_short.md" \
  "work/stream/groq_outputs/stream_summary_source.md" \
  --output "work/stream/summary_outputs/stream_context_links.md" \
  --limit 12
```

Этот фолбэк-скрипт ищет в тексте совпадения из фиксированного словаря вечнозелёных тем
(безопасность, гифты, роли в Discord и т.д.) плюс явные домены через regex - он не знает
про уникальные для стрима материалы, если агент не подготовил `summary_mentioned_materials.md`.
Итоговый блок в любом случае рендерится списком через `•` без URL.

Чтобы собрать файлы для выгрузки:

```bash
python3 scripts/build_final_digest.py "work/stream" stream --limit 12
```

Он создаёт:

- `summary_outputs/stream_summary_short_with_links.md` — укороченная выжимка и ниже блок полезных тем.
- `summary_outputs/stream_summary_with_links.md` — длинная выжимка с блоком полезных тем, только если существует `summary_outputs/stream_summary.md`.

## Формат финальных файлов

`summary_outputs/<stem>_summary.md`:

- ровно N строк, где N указано в `meta.json` как `summary_source_lines`
- формат строки: `HH:MM:SS  Глагол конкретика`
- два пробела после таймкода
- без markdown-маркеров, скобок, кавычек и эмодзи
- используется как исходник для `<stem>_summary_with_links.md`
- опциональный файл, готовится только по запросу на длинную выжимку

`summary_outputs/<stem>_summary_intermediate.md`:

- обязательный технический файл для контроля контекста
- содержит N блоков из `groq_outputs/<stem>_summary_source.md`
- перед каждым сырым блоком идёт заголовок `## HH:MM:SS Короткое описание блока`
- описание пишется в стиле короткой выжимки: компактно, но с явной темой таймкода
- не содержит блок `Полезные ссылки из чата`

`summary_outputs/<stem>_summary_short.md`:

- 19-24 строки
- не больше 4000 символов
- один пробел после таймкода
- без точки в конце каждой строки
- без заголовков разделов и пустых строк - сплошной список
- каждая строка соответствует смысловому блоку стрима, таймкод берётся с момента начала блока
- подавать тезисы от лица спикеров через `мы`, а не через `автор`
- используется как исходник для `<stem>_summary_short_with_links.md`

`summary_outputs/<stem>_summary_mentioned_materials.md`:

- список реальных инструментов/сервисов/проектов, упомянутых в этом стриме
- формат строки: `• Название`, без URL
- готовит LLM-агент по `summary_source.md`, не скрипт
- если файл существует, `build_final_digest.py` строит из него блок `Полезные ссылки из чата`
  вместо автоматического поиска по фиксированному словарю

`summary_outputs/<stem>_summary_with_links.md`:

- начинается с содержимого `<stem>_summary.md`
- после выжимки содержит блок `Полезные ссылки из чата`
- блок тем идёт списком через `•` без URL
- создаётся только если существует `<stem>_summary.md`

`summary_outputs/<stem>_summary_short_with_links.md`:

- начинается с содержимого `<stem>_summary_short.md`
- после короткой выжимки содержит блок `Полезные ссылки из чата`
- блок тем идёт списком через `•` без URL

## README MAP

- `scripts/groq_transcribe.py` — транскрипция одного аудиофайла с resume-логикой.
- `scripts/merge_groq_parts.py` — слияние частей и генерация `summary_source.md`.
- `scripts/build_intermediate_digest.py` — сборка технической промежуточной выжимки из N сырых блоков и N описаний.
- `scripts/build_context_links.py` — фолбэк-генератор блока контекстных ссылок по фиксированному словарю тем, используется только если агент не подготовил `summary_mentioned_materials.md`.
- `scripts/build_final_digest.py` — сборка короткой версии с блоком тем (из `summary_mentioned_materials.md` либо фолбэком через `build_context_links.py`); длинной версии только при наличии `summary.md`.
- `scripts/build_ama_timecodes.py` — построение кандидатов и проверенных таймкодов АМА, а также вопросного `ama_source.md`.
- `scripts/segment_lookup.py` — точный поиск таймкода по `{stem}_segments.json` (сегменты Whisper, ~5-15 сек) через `--search "фраза"` или `--around ЧЧ:ММ:СС --window N`; обязателен при разметке `summary_short.md`, чтобы не брать таймкод на глаз из склеенного `transcript.txt`.
- `scripts/smoke_test.py` — короткая проверка Groq API перед длинным прогоном.
- `scripts/validate_outputs.py` — проверка обязательных артефактов.
- `.claude/skills/summarize.md` — агентский скилл: Claude читает `summary_source.md`, генерирует выжимку по правилам формата, список реально упомянутых материалов и запускает build-скрипты. Вызывается через `/summarize` или автоматически при любой просьбе «сделать выжимку» в проекте.
- `tests/test_merge_groq_parts.py` — локальный тест слияния частей.
- `tests/test_build_context_links.py` — локальный тест генератора контекстных ссылок.
- `tests/test_build_final_digest.py` — локальный тест сборки short-first выдачи и опциональной длинной версии с блоком тем.
- `tests/test_build_ama_timecodes.py` — тест кандидатов, проверенных границ и АМА-валидации.
- `tests/test_segment_lookup.py` — тест точного поиска таймкода по сегментам.
- `CHANGELOG.md` — сжатое System State проекта.
- `input/` — локальные входные аудиофайлы, не коммитятся.
- `work/` — рабочие результаты, не коммитятся.
- `.secrets/` — локальные ключи, не коммитятся.

## Команды тестирования

```bash
python3 -m unittest discover -s tests
```
