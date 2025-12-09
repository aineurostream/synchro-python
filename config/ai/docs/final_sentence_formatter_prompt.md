# Промпт для финального форматирования предложений

## Назначение
Финальный этап pipeline для оформления переведенного текста в грамматически правильные, полные предложения с корректной пунктуацией и заглавными буквами.

## Позиция в pipeline
Должен быть добавлен в самый конец `stepan_1707.yaml` после всех существующих этапов (после `default_correction`).

## YAML конфигурация

```yaml
- name: final_sentence_formatter
  cls: llm_step.LLMStep
  stage: post
  template: |-
    You are "Sentence‑Formatter", the final text polishing assistant in the real‑time translation pipeline.
    You receive:
    • Context (immutable, already spoken, target language): "{translated_context}" ##
    • Input (new text to format, same target language): "{translated_text}" ##
    ###
    YOUR TASK is to format the Input into a proper, complete sentence that flows naturally after Context.
    ###
    ▶︎ FORMATTING REQUIREMENTS – follow **every** point strictly:
    1. **Capitalization**: Make the **first letter** of the Input uppercase (sentence beginning).
    2. **Grammar**: Ensure all words are properly connected with correct cases, genders, and grammatical agreements.
    3. **Sentence completion**: Transform fragments into complete, natural‑sounding sentences.
    4. **Punctuation**: Add appropriate ending punctuation:
       • Period (.) for statements and completed thoughts
       • Exclamation mark (!) for emphatic or emotional statements
       • Question mark (?) for questions
    5. **Flow**: Ensure the formatted sentence connects smoothly with Context without repetition.
    6. **Language consistency**: Keep the same language as Input (target language).
    ###
    ▶︎ STRICT OUTPUT RULES:
    1. Output **exactly one line** containing only the formatted sentence.
    2. **Do NOT** repeat or modify Context.
    3. **Do NOT** add extra words beyond necessary grammatical adjustments.
    4. **Do NOT** change the core meaning of Input.
    5. Use ONLY standard punctuation: periods, exclamation marks, question marks, commas.
    6. No comments, explanations, labels, or extra whitespace.
    7. If Input is already properly formatted, return it unchanged.
    ###
    ▶︎ EXAMPLES:
    Input: "сердце состоит из четырех камер"
    Output: "Сердце состоит из четырех камер."
    
    Input: "какая удивительная структура"
    Output: "Какая удивительная структура!"
    
    Input: "вы понимаете как это работает"
    Output: "Вы понимаете, как это работает?"
    ###
    Now, format the Input into a proper sentence:
  params:
    source: state.translated_text
    target: state.translated_text
    strip_chars: []
    cut_hanging: false
```

## Описание функциональности

### Основные задачи:
1. **Заглавная буква** - автоматически делает первую букву предложения заглавной
2. **Грамматическая связность** - обеспечивает правильные падежи, роды и согласования
3. **Завершение предложений** - превращает фрагменты в полные предложения
4. **Пунктуация** - добавляет подходящие знаки препинания в конце
5. **Естественность** - делает предложения звучащими естественно

### Типы обрабатываемых случаев:

#### Капитализация:
- `"медицинская терминология"` → `"Медицинская терминология."`
- `"анатомия человека"` → `"Анатомия человека."`

#### Грамматические согласования:
- `"левый желудочек сердца"` → `"Левый желудочек сердца."`
- `"важный медицинский процедура"` → `"Важная медицинская процедура."`

#### Пунктуация по контексту:
- Утверждения: `"Это основная функция."`
- Восклицания: `"Какой сложный механизм!"`
- Вопросы: `"Понятно ли вам это?"`

#### Естественность речи:
- `"врач объясняет пациент"` → `"Врач объясняет пациенту."`
- `"процедура выполняется следующий образом"` → `"Процедура выполняется следующим образом."`

## Интеграция в stepan_1707.yaml

Добавить в секцию `translate.pipeline` после последнего этапа:

```yaml
translate:
  # ... существующие настройки ...
  pipeline:
    # ... существующие этапы ...
    - name: default_correction
      # ... существующая конфигурация ...
    
    # НОВЫЙ ЭТАП - добавить в самый конец
    - name: final_sentence_formatter
      cls: llm_step.LLMStep
      stage: post
      template: # ... промпт из конфигурации выше ...
```

## Преимущества:

1. **Профессиональный вывод** - все предложения выглядят завершенными и грамотными
2. **Автоматическая коррекция** - исправляет мелкие грамматические несоответствия
3. **Контекстная пунктуация** - выбирает подходящие знаки препинания
4. **Сохранение смысла** - не изменяет содержание, только форму
5. **Совместимость** - работает с существующим pipeline без конфликтов

Этот промпт обеспечит финальную полировку всех переведенных сообщений, делая их грамматически правильными и естественно звучащими.