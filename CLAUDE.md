# CLAUDE.md — выжимки стримов

## Проект

Локальный Python-пайплайн для транскрипции аудиостримов LifeChange через Groq Whisper
и подготовки готовых выжимок с таймкодами.

Рабочий каталог: `<project-root>`

## Автоматический триггер выжимки

Если пользователь в этом проекте пишет что-либо похожее на:

- «сделай выжимку»
- «сделай summary»
- «обработай стрим»
- «сводку по стриму»
- «summary для [stem]»
- или любую аналогичную формулировку

→ Немедленно выполнить скилл `.claude/skills/summarize.md` без запроса подтверждения
  и без ожидания явного вызова `/summarize`.

Это основной рабочий режим проекта. Выжимка — это всегда скилл summarize.

## Скрипты

Все скрипты запускаются из корня проекта:

| Скрипт | Назначение |
|---|---|
| `scripts/groq_transcribe.py` | Транскрипция аудио через Groq Whisper |
| `scripts/merge_groq_parts.py` | Слияние частей + генерация summary_source.md |
| `scripts/build_intermediate_digest.py` | Сборка промежуточной выжимки (48 блоков + метки) |
| `scripts/build_final_digest.py` | Сборка финальных файлов с блоком тем |
| `scripts/validate_outputs.py` | Проверка артефактов |
| `scripts/smoke_test.py` | Быстрая проверка Groq API |

## Структура work/

```
work/{stem}/
  groq_outputs/
    {stem}_segments.json        — сырые сегменты транскрибации
    {stem}_transcript.txt       — транскрибация с таймкодами
    {stem}_summary_source.md    — N блоков для выжимки (входной файл скилла)
    {stem}_meta.json            — метаданные, включая summary_source_lines
  summary_outputs/
    {stem}_summary_intermediate_notes.md   — метки для каждого блока (пишет скилл)
    {stem}_summary_intermediate.md         — технический файл (пишет build_intermediate_digest)
    {stem}_summary_short.md                — короткая выжимка (пишет скилл)
    {stem}_summary_short_with_links.md     — финал для выгрузки (пишет build_final_digest)
    {stem}_summary.md                      — длинная выжимка, опционально
    {stem}_summary_with_links.md           — длинный финал, только если есть summary.md
```

## Безопасность

- Groq API ключи не логировать и не выводить в консоль
- Ключи живут в `.env` или `.secrets/groq_primary.key` / `.secrets/groq_fallback.key`
