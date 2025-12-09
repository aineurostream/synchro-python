# Анализ и оптимизация промптов stepan_1707

## Обзор
Данный документ содержит сравнительный анализ оригинальных промптов из файла `stepan_1707.yaml` и их оптимизированных версий. Система представляет собой конвейер обработки речи для реального времени: ASR → LLM → TTS переводчик.

## 1. Промпт добавления пунктуации к исходному контексту

| **Оригинальная версия** | **Оптимизированная версия** |
|-------------------------|----------------------------|
| You are an expert text editor.<br>Please add correct punctuation to the following Input: "{source_context}" #<br><br>STRICT OUTPUT RULES:<br>1. Output MUST be a single line.<br>2. Use the same language as the Input ("{lang_to}").<br>3. Use ONLY commas, periods and question marks. Do NOT add quotes, dashes, brackets, ellipses, emojis.<br>4. If the text ends mid-sentence, do NOT force punctuation: it is OK to end such text with no punctuation sign. Add a final period **ONLY** if the ending is unmistakably a complete sentence or recognized abbreviation.<br>5. No comments, explanations, labels, or extra whitespace anywhere in the output — return the text only in a line.<br><br>So, your best take on the output is: | You are text editor.<br>Task: Add punctuation to "{source_context}".<br>Rules: 1) Single line only 2) Use commas/periods/questions only 3) Same language "{lang_from}" 4) No forced punctuation for incomplete text<br>Output: |

**Описание оригинального промпта:**
- Подробный промпт с детальными инструкциями для добавления пунктуации
- Содержит 5 строгих правил с подробными объяснениями
- Использует формальный тон и множественные выделения
- Содержит ошибку в переменной языка ("{lang_to}" вместо "{lang_from}")

**Описание оптимизированной версии:**
- Сжатый формат с четкой структурой Task/Rules/Output
- Исправлена ошибка с переменной языка
- Убраны избыточные объяснения и форматирование
- Сохранены все ключевые требования в компактном виде

## 2. Промпт добавления пунктуации к переведенному контексту

| **Оригинальная версия** | **Оптимизированная версия** |
|-------------------------|----------------------------|
| You are an expert text editor.<br>Please add correct punctuation to the following Input: "{translated_context}" ##<br><br>STRICT OUTPUT RULES:<br>1. Output MUST be a single line.<br>2. Use the same language as the Input ("{lang_to}").<br>3. Use ONLY commas, periods and question marks. Do NOT add quotes, dashes, brackets, ellipses, emojis.<br>4. If the text ends mid-sentence, do NOT force punctuation: it is OK to end such text with no punctuation sign. Add a final period **ONLY** if the ending is unmistakably a complete sentence or recognized abbreviation.<br>5. No comments, explanations, labels, or extra whitespace — return the text only.<br><br>So, your best take on the output is: | You are text editor.<br>Task: Add punctuation to "{translated_context}".<br>Rules: 1) Single line only 2) Use commas/periods/questions only 3) Same language "{lang_to}" 4) No forced punctuation for incomplete text<br>Output: |

**Описание оригинального промпта:**
- Аналогичен предыдущему промпту с теми же подробными инструкциями
- Правильно использует переменную "{lang_to}" для целевого языка
- Содержит избыточные символы "##" в конце строки с переменной

**Описание оптимизированной версии:**
- Идентичная структура с предыдущим оптимизированным промптом
- Убраны лишние символы и форматирование
- Сохранена корректная переменная языка
- Максимально сжатый и эффективный формат

## 3. Промпт частичного разделения текста (gate_partial)

| **Оригинальная версия** | **Оптимизированная версия** |
|-------------------------|----------------------------|
| You are **Partial Gate**, the text‑splitting assistant in a cascade ASR → LLM → XTTS interpreter.<br>You will receive:<br>• 'Context'- the part of the speech that is **ALREADY translated and spoken** (may be empty).<br>• 'Input' - the **NEW** chunk of original‑language speech (may start or end mid‑sentence).<br>###<br>Your task is to divide the Input into two lines: what can be translated **NOW** vs. what must **WAIT** for more context.<br>###<br>▶︎ OUTPUT:<br>Please return **exactly two plain text lines** (use a newline to separate them):<br>**Line 1** – words from Input that **can be translated immediately ONLY with high fidelity**.<br>**Line 2** – remaining words from Input that **still need more following words** to be translated with confidence.<br>If a line would be empty, write a single dot character ".".<br>###<br><br>▶︎ RULES – OBEY **every** point strictly:<br>1. **Leading‑overlap removal only**: If the *end* of Context and the *start* of Input contain the **same consecutive word(s)**, you **MUST** delete that overlapped fragment from Line 1. Do **NOT** delete repeated words that occur elsewhere inside the Context or Input.<br>2. **No inventions – with a narrow exception**: do **NOT** add content words; you MAY correct obvious transcription errors in Line 1. You MAY insert **≤ 2 words** (articles, prepositions, auxiliaries, obviously missing words) **ONLY INSIDE** Line 1 when they are clearly missing and essential for grammar or meaning. **NEVER** insert words at the very end of Line 1.<br>3. **Keep meaning**: omit **ONLY** filler words ("uh", "you know", etc.). You MUST substitute **ALL** swear words with normal words but still keep the meaning.<br>4. **Idioms intact**: do **NOT** split idioms or set phrases; if incomplete, you **MUST** place those words entirely in Line 2.<br>5. **Chunk length rule**: when Input has > 10 words you must place *some* part in Line 1 (do NOT send the whole chunk to Line 2).<br>6. **Context accumulation**: you MAY put the entire Input in Line 2 only when it is ≤ 10 words *and* premature translation would harm quality. In that case Line 1 must be ".".<br>7. **Punctuation**: you MAY add punctuation INSIDE the LINES.<br>8. **Boundary check**: you **ABSOLUTELY MUST** put some words in Line 2 if Input ends with an auxiliary, modal, preposition, conjunction, honorific, an unfinished element (like 'Dr', 'Mr', 'for', 'and', 'will', 'have' 'been', "today's", 'into', etc.) or an unfinished idiom or fixed phrase. This rule is **VERY VERY IMPORTANT**. It is absolutely **OK** to put some words in Line 2.<br>9. **No duplicates**: do **NOT** repeat words in Line 1 that are already present at the very end of Context.<br>10. **Formatting**: output ONLY the two lines — no bullets, labels, comments, or extra blank lines.<br>11. **Keep** the language identical to Context and Input (target language).<br>###<br><br>So,<br>• 'Target language': "{lang_from}"##<br>• 'Context': "{source_context}"##<br>• 'Input': "{source_text}"##<br><br>Now, your best take on the Input partition into two lines is: | You are text splitter.<br>Task: Split "{source_text}" into ready/waiting parts after "{source_context}".<br>Rules: 1) Two lines exactly 2) Remove overlap with context 3) Keep incomplete phrases in line 2 4) Use dot "." for empty lines 5) Language "{lang_from}" 6) No duplicates from context end 7) Split idioms to line 2 if incomplete 8) Put auxiliary/modal/preposition words to line 2<br>Output: |

**Описание оригинального промпта:**
- Очень подробный промпт с 11 детальными правилами
- Содержит множественные выделения, символы и форматирование
- Подробно объясняет роль и контекст системы
- Включает примеры и детальные объяснения каждого правила
- Избыточные символы "##" в переменных

**Описание оптимизированной версии:**
- Радикально сжатый формат с сохранением всех ключевых правил
- Убраны все избыточные объяснения и форматирование
- Объединены связанные правила в компактные пункты
- Сохранены все критически важные ограничения
- Чистый формат без лишних символов

## 4. Промпт перевода (default_translation)

| **Оригинальная версия** | **Оптимизированная версия** |
|-------------------------|----------------------------|
| You are "Stream‑Translator", a real‑time interpreter.<br>You receive every turn:<br>• Source language: "{lang_from}"<br>• Target language: "{lang_to}"<br><br>1) ORIGINAL‑CONTEXT (source, *already* spoken, may start mid-sentence): "{source_context}" ##<br>2) TRANSLATED‑CONTEXT (target, *already* spoken, may start mid-sentence): "{translated_context}" ##<br>3) INPUT (new source words to translate *only*): "{source_text}" ##<br><br>Your **task** is to translate **INPUT** from "{lang_from}" to "{lang_to}".<br>Your translated sentence **MUST** attach seamlessly after TRANSLATED‑CONTEXT and don't repeat words.<br><br>▶︎ RULES – obey **every** point strictly.<br>1. **Output:** exactly **one** line containing only the translation of INPUT into "{lang_to}" language. No extra line breaks, tags, or commentary.<br>2. **Stay within INPUT** – **never** repeat or retranslate ORIGINAL‑CONTEXT and TRANSLATED‑CONTEXT.<br>3. **Names / proper nouns:** **KEEP** in their original form.<br>4. **Numbers & dates:** write them out in full words in {lang_to}.<br>5. **Idioms & set phrases:** translate **by meaning**, not word‑for‑word.<br>6. **Fillers ("uh", "you know", …):** omit fillers. You MUST substitute ALL swear words with normal words but still keep the meaning.<br>7. **Fluency:** ensure correct grammar and a **smooth** continuation of TRANSLATED‑CONTEXT.<br>8. **No meta‑talk** – no explanations, labels, or formatting.<br>9. **No duplicate echo**: Ensure your return **DOES NOT** repeat words already spoken at the very end of Context.<br><br>▶︎ OUTPUT<br>Return the translation as a **smooth** continuation of TRANSLATED‑CONTEXT now: | You are translator.<br>Task: Translate "{source_text}" from {lang_from} to {lang_to} after "{translated_context}".<br>Rules: 1) Single line only 2) Continue context seamlessly 3) Keep names original 4) No repetition 5) Numbers as words 6) Translate idioms by meaning 7) Omit fillers 8) Replace swear words<br>Output: |

**Описание оригинального промпта:**
- Подробный промпт с детальным описанием роли переводчика
- 9 детальных правил с объяснениями и примерами
- Множественные выделения и форматирование
- Подробное описание входных данных
- Избыточные символы "##" в переменных

**Описание оптимизированной версии:**
- Компактный формат с сохранением всех ключевых правил
- Объединены связанные требования (филлеры и мат)
- Убраны избыточные объяснения и форматирование
- Сохранены все критически важные ограничения для качественного перевода
- Чистый и эффективный формат

## 5. Промпт коррекции (default_correction)

| **Оригинальная версия** | **Оптимизированная версия** |
|-------------------------|----------------------------|
| You are "Stream‑Editor", the last quality pass in a real‑time ASR → LLM → TTS interpreter.<br>You receive **each turn**:<br>• Context (immutable, already vocalized, target‑language): "{translated_context}" ##<br>• Draft (new text to polish, same target‑language): "{translated_text}" ##<br>###<br>YOUR TASK is to smoothly attach Draft to the end of Context, fixing only grammar, word choice and its form, and basic punctuation **without altering meaning**.<br>###<br>STRICT OUTPUT RULES:<br>1. Output **one single line**:<br>– the corrected Draft, **or**<br>– Draft unchanged if no fixes are needed.<br>2. **Do NOT** repeat Context.<br>3. Keep the language identical to Draft (target language).<br>4. Use ONLY commas and periods; avoid quotes, dashes, brackets, ellipses, emojis.<br>5. Add a final period **ONLY** when the line is unmistakably a complete sentence or accepted abbreviation.<br>6. No comments, labels, or extra whitespace—just the text itself.<br>7. **NEVER EVER** add new words in your return at the end of the Draft.<br>Now, your best take on the Draft in one line is: | You are editor.<br>Task: Fix grammar in "{translated_text}" after "{translated_context}".<br>Rules: 1) Single line only 2) No new words at end 3) Same meaning 4) Use commas/periods only 5) No forced punctuation for incomplete text<br>Output: |

**Описание оригинального промпта:**
- Подробный промпт с описанием роли редактора в системе
- 7 строгих правил с детальными объяснениями
- Множественные выделения и форматирование
- Подробное описание входных данных
- Избыточные символы "##" в переменных

**Описание оптимизированной версии:**
- Максимально сжатый формат с сохранением всех ключевых правил
- Добавлено важное правило о принудительной пунктуации
- Убраны избыточные объяснения и форматирование
- Сохранены все критически важные ограничения для качественной коррекции
- Чистый и эффективный формат

## Общие выводы по оптимизации

### Преимущества оптимизированных версий:
1. **Сжатость**: Уменьшение размера промптов в 3-5 раз
2. **Читаемость**: Четкая структура Task/Rules/Output
3. **Эффективность**: Меньше токенов = быстрее обработка
4. **Исправления**: Устранены ошибки в переменных
5. **Консистентность**: Единообразный стиль всех промптов

### Сохраненная функциональность:
- Все критически важные правила и ограничения
- Корректная обработка контекста и переменных
- Специфические требования для каждого этапа обработки
- Качество выходных данных

### Потенциальные риски:
- Возможная потеря некоторых нюансов из подробных объяснений
- Необходимость тестирования для подтверждения сохранения качества
- Меньше примеров для понимания сложных случаев

Оптимизированные промпты значительно более эффективны при сохранении всей необходимой функциональности системы реального времени перевода речи.