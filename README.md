# Выжимки стримов LifeChange

Локальный пайплайн для транскрипции `.ogg`-стримов через Groq Whisper и подготовки исходника для итоговой выжимки.

## Что делает проект

1. Режет один аудиофайл на короткие чанки.
2. Отправляет чанки в Groq `whisper-large-v3-turbo`.
3. Инкрементально сохраняет сегменты, чтобы можно было продолжить после сбоя.
4. Склеивает одну или несколько частей стрима.
5. Создаёт `summary_source.md` из 48 равных временных блоков.
6. LLM-агент готовит короткую выжимку и техническую промежуточную выжимку.
7. После AI-выжимки ищет по транскрибации темы, сервисы и инструменты для блока `Полезные ссылки из чата`.
8. Собирает короткую версию для выгрузки с блоком полезных тем.
9. Собирает длинную версию только если вручную подготовлен `<stem>_summary.md`.
10. Проверяет готовые артефакты перед сдачей.

`summary_short.md` и `summary_intermediate.md` собираются LLM-агентом по `summary_source.md`. После этого локальный скрипт добавляет блок тем по транскрибации и создаёт короткую версию для выгрузки. Длинная `summary.md` собирается только по отдельному запросу; если она есть, скрипт дополнительно создаёт длинную версию с блоком тем.

## Технологии

- Язык: Python 3
- Внешние утилиты: `ffmpeg`, `ffprobe`
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

## Полезные ссылки из чата

После подготовки выжимки можно собрать дополнительный текстовый блок тем, сервисов и инструментов:

```bash
python3 scripts/build_context_links.py \
  "work/stream/summary_outputs/stream_summary_short.md" \
  "work/stream/groq_outputs/stream_summary_source.md" \
  --output "work/stream/summary_outputs/stream_context_links.md" \
  --limit 12
```

Скрипт ищет в тексте заметные сервисы, инструменты, домены и темы, затем создаёт блок `Полезные ссылки из чата` списком через `•` без URL. В рабочем цикле этот блок строится по полной транскрибации через `build_final_digest.py`.

Чтобы собрать файлы для выгрузки:

```bash
python3 scripts/build_final_digest.py "work/stream" stream --limit 12
```

Он создаёт:

- `summary_outputs/stream_summary_short_with_links.md` — укороченная выжимка и ниже блок полезных тем.
- `summary_outputs/stream_summary_with_links.md` — длинная выжимка с блоком полезных тем, только если существует `summary_outputs/stream_summary.md`.

## Формат финальных файлов

`summary_outputs/<stem>_summary.md`:

- ровно 48 строк
- формат строки: `HH:MM:SS  Глагол конкретика`
- два пробела после таймкода
- без markdown-маркеров, скобок, кавычек и эмодзи
- используется как исходник для `<stem>_summary_with_links.md`
- опциональный файл, готовится только по запросу на длинную выжимку

`summary_outputs/<stem>_summary_intermediate.md`:

- обязательный технический файл для контроля контекста
- содержит 48 блоков из `groq_outputs/<stem>_summary_source.md`
- перед каждым сырым блоком идёт заголовок `## HH:MM:SS Короткое описание блока`
- описание пишется в стиле короткой выжимки: компактно, но с явной темой таймкода
- не содержит блок `Полезные ссылки из чата`

`summary_outputs/<stem>_summary_short.md`:

- 19-24 строки
- не больше 4000 символов
- один пробел после таймкода
- точка в конце каждой строки
- используется как исходник для `<stem>_summary_short_with_links.md`

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
- `scripts/build_intermediate_digest.py` — сборка технической промежуточной выжимки из 48 сырых блоков и 48 описаний.
- `scripts/build_context_links.py` — генерация короткого блока контекстных ссылок по выжимке.
- `scripts/build_final_digest.py` — сборка короткой версии с блоком тем; длинной версии только при наличии `summary.md`.
- `scripts/smoke_test.py` — короткая проверка Groq API перед длинным прогоном.
- `scripts/validate_outputs.py` — проверка обязательных артефактов.
- `tests/test_merge_groq_parts.py` — локальный тест слияния частей.
- `tests/test_build_context_links.py` — локальный тест генератора контекстных ссылок.
- `tests/test_build_final_digest.py` — локальный тест сборки short-first выдачи и опциональной длинной версии с блоком тем.
- `CHANGELOG.md` — сжатое System State проекта.
- `input/` — локальные входные аудиофайлы, не коммитятся.
- `work/` — рабочие результаты, не коммитятся.
- `.secrets/` — локальные ключи, не коммитятся.

## Команды тестирования

```bash
python3 -m unittest discover -s tests
```
