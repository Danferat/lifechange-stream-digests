# AGENTS.md — выжимки стримов

## Проект

Локальный Python-пайплайн для транскрипции аудиостримов LifeChange через Groq Whisper
и подготовки готовых выжимок с таймкодами.

Рабочий каталог: `<project-root>`

## Выбор режима

Доступны два режима:

- `обычная выжимка` - выполнить `.claude/skills/summarize.md`
- `AMA-таймкоды` - выполнить `.claude/skills/ama_timecodes.md`; обязательны скрины вопросов

Если пользователь упоминает АМА, но не выбрал режим, сначала спросить: «Обычная выжимка или таймкоды вопросов АМА?»

## Автоматический триггер: обычная выжимка

Если пользователь пишет что-либо похожее на:

- «сделай выжимку»
- «сделай summary»
- «обработай стрим»
- «сводку по стриму»
- «summary для [stem]»
- или любую аналогичную формулировку без упоминания АМА

→ Немедленно выполнить скилл `.Codex/skills/summarize.md` без запроса подтверждения
  и без ожидания явного вызова `/summarize`.

Это основной рабочий режим проекта. Для обычной выжимки используется summarize; АМА обрабатывается только после явного выбора режима.

## Скрипты

Все скрипты запускаются из корня проекта:

| Скрипт | Назначение |
|---|---|
| `scripts/groq_transcribe.py` | Транскрипция аудио через Groq Whisper |
| `scripts/merge_groq_parts.py` | Слияние частей + генерация summary_source.md |
| `scripts/build_intermediate_digest.py` | Сборка промежуточной выжимки (N блоков + метки) |
| `scripts/build_final_digest.py` | Сборка финальных файлов с блоком тем |
| `scripts/build_ama_timecodes.py` | Кандидаты и проверенные границы вопросов АМА |
| `scripts/validate_outputs.py` | Проверка артефактов |
| `scripts/smoke_test.py` | Быстрая проверка Groq API |

## Структура work/

```
work/{stem}/
  groq_outputs/
    {stem}_segments.json        — сырые сегменты транскрибации
    {stem}_transcript.txt       — транскрибация с таймкодами
    {stem}_summary_source.md    — N блоков для выжимки (входной файл скилла)
    {stem}_ama_source.md        — текст АМА, разбитый по вопросам после проверки
    {stem}_meta.json            — метаданные, включая summary_source_lines
  summary_outputs/
    {stem}_summary_intermediate_notes.md   — метки для каждого блока (пишет скилл)
    {stem}_summary_intermediate.md         — технический файл (пишет build_intermediate_digest)
    {stem}_summary_short.md                — короткая выжимка (пишет скилл)
    {stem}_summary_short_with_links.md     — финал для выгрузки (пишет build_final_digest)
    {stem}_summary.md                      — длинная выжимка, опционально
    {stem}_summary_with_links.md           — длинный финал, только если есть summary.md
    {stem}_ama_timecodes.md                — проверенные таймкоды вопросов АМА
```

## Безопасность

- Groq API ключи не логировать и не выводить в консоль
- Ключи живут в `.env` или `.secrets/groq_primary.key` / `.secrets/groq_fallback.key`
