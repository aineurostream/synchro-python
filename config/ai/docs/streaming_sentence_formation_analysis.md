# Глубокий анализ формирования предложений в потоковой системе перевода

## Анализ исходного текста "ДО" в контексте потоковой обработки

### Характеристики входного текста

#### 1. Структура потока речи
```
произойти сигналом добродетели, нападая на всё предприятие, говоря что зарабатывание денег — это зло и вам не следует этого делать, но то, что они пытаются сделать — это на самом деле игра в другую игру игра статуса они пытаются казаться людьми высокого статуса...
```

**Особенности:**
- **Отсутствие пунктуации** - результат `remove_punctuation` этапа
- **Слитный поток** - естественная речь без искусственных пауз
- **Логические блоки** - идеи группируются по смыслу, не по грамматике
- **Переходы мыслей** - естественные связки между концепциями

#### 2. Семантическая структура
Текст содержит несколько крупных смысловых блоков:

1. **Критика добродетельного сигналинга** (начало)
2. **Объяснение игр статуса vs богатства** (основная часть)
3. **Исторический контекст** (охотники-собиратели → фермеры)
4. **Современные примеры** (журналисты, технологии)
5. **Философские выводы** (паразиты vs создатели)

### Анализ stepan_1707.yaml в контексте потоковой обработки

#### Текущий pipeline и его ограничения:

```yaml
pipeline:
  1. add_punctuation_to_source_context    # Добавляет пунктуацию к контексту
  2. add_punctuation_to_translated_context # Добавляет пунктуацию к переводу
  3. remove_punctuation                   # УДАЛЯЕТ всю пунктуацию
  4. strip_chars                         # Очищает символы
  5. gate_partial                        # Делит на части для перевода
  6. default_translation                 # Переводит части
  7. default_correction                  # Корректирует перевод
```

#### Проблемы текущего подхода:

1. **Противоречивость**: Сначала добавляем пунктуацию, потом удаляем
2. **Потеря границ предложений**: `remove_punctuation` уничтожает структуру
3. **Фрагментарный перевод**: `gate_partial` не учитывает семантические границы
4. **Отсутствие финальной сборки**: Нет этапа объединения фрагментов в предложения

## Анализ потоковых ограничений

### 1. ASR (Speech-to-Text) ограничения
```yaml
stt:
  buffer_min_words_size: 5      # Минимум 5 слов в буфере
  buffer_timeout_seconds: 2.0   # Таймаут 2 секунды
```

**Проблемы:**
- ASR выдает фрагменты по времени/размеру, не по смыслу
- Границы фрагментов случайны относительно предложений
- Нет информации о паузах в речи

### 2. LLM обработка
```yaml
translate:
  context_window_words: 35      # Окно контекста 35 слов
  temperature: 0.1              # Низкая температура для стабильности
```

**Ограничения:**
- Фиксированное окно контекста может разрывать предложения
- Каждый фрагмент переводится независимо
- Нет глобального понимания структуры текста

### 3. TTS (Text-to-Speech) требования
```yaml
tts:
  gap_size_bytes: 8000         # Размер пауз между фрагментами
```

**Проблемы:**
- TTS нужны завершенные предложения для естественной интонации
- Фрагменты без пунктуации звучат монотонно
- Отсутствие пауз между предложениями

## Предлагаемое решение: Система накопления и формирования предложений

### Концепция: Двухуровневая обработка

#### Уровень 1: Потоковый перевод (существующий)
- Быстрая обработка фрагментов для минимальной задержки
- Сохранение текущей скорости системы
- Накопление переведенных фрагментов

#### Уровень 2: Формирование предложений (новый)
- Анализ накопленных фрагментов
- Определение границ предложений
- Финальное форматирование

### Новый этап pipeline: `sentence_accumulator`

```yaml
- name: sentence_accumulator
  cls: sentence_accumulator_step.SentenceAccumulatorStep
  template: |-
    You are "Sentence‑Accumulator", a text assembly specialist in real‑time translation pipeline.
    
    You receive:
    • Accumulated fragments: "{accumulated_fragments}" ##
    • New fragment: "{translated_text}" ##
    • Context window: "{context_window}" ##
    
    Your task is to determine if accumulated fragments + new fragment form complete sentences that can be output.
    
    ▶︎ ANALYSIS RULES:
    1. **Semantic completeness**: Check if fragments form complete thoughts
    2. **Logical flow**: Ensure smooth transitions between ideas  
    3. **Natural boundaries**: Identify natural sentence breaks
    4. **Context preservation**: Maintain meaning across fragments
    
    ▶︎ OUTPUT FORMAT:
    Line 1: READY_SENTENCES (complete sentences to output, or "NONE")
    Line 2: KEEP_BUFFER (fragments to keep for next iteration, or "NONE")
    
    ▶︎ SENTENCE FORMATION RULES:
    1. **Minimum completeness**: At least one complete thought
    2. **Maximum delay**: No more than 10 fragments without output
    3. **Natural breaks**: Use semantic cues (topic changes, conclusions)
    4. **Proper capitalization**: First word capitalized
    5. **Appropriate punctuation**: Period, exclamation, or question mark
    
    Now analyze the fragments:
  params:
    max_buffer_fragments: 10
    min_sentence_words: 8
    accumulation_timeout: 15
```

### Новый этап: `sentence_formatter`

```yaml
- name: sentence_formatter  
  cls: llm_step.LLMStep
  stage: post
  template: |-
    You are "Sentence‑Formatter", the final sentence polishing specialist.
    
    You receive ready sentence fragments: "{ready_sentences}" ##
    
    Your task is to format these fragments into proper, natural sentences.
    
    ▶︎ FORMATTING RULES:
    1. **Capitalization**: First letter of each sentence uppercase
    2. **Punctuation**: Appropriate ending punctuation (. ! ?)
    3. **Flow**: Ensure smooth connections between sentences
    4. **Grammar**: Correct any minor grammatical issues
    5. **Naturalness**: Make sentences sound natural and complete
    
    ▶︎ STRICT CONSTRAINTS:
    1. **No content changes**: Don't add or remove meaning
    2. **No reordering**: Keep the original sequence
    3. **Minimal edits**: Only essential formatting changes
    4. **Language consistency**: Maintain target language
    
    ▶︎ OUTPUT:
    Return properly formatted sentences, one per line.
    
    Format the sentences:
  params:
    strip_chars: []
    preserve_meaning: true
```

## Обновленная архитектура pipeline

### Новая последовательность этапов:

```yaml
translate:
  pipeline:
    # Этап 1-3: Подготовка (без изменений)
    - name: remove_punctuation
    - name: strip_chars  
    - name: gate_partial
    
    # Этап 4-5: Перевод (без изменений)
    - name: default_translation
    - name: default_correction
    
    # НОВЫЕ ЭТАПЫ: Формирование предложений
    - name: sentence_accumulator     # Накопление и анализ фрагментов
    - name: sentence_formatter       # Финальное форматирование
    
    # Этап 6: Вывод готовых предложений
    - name: sentence_output          # Вывод в TTS
```

### Логика работы накопителя:

#### Состояния системы:
1. **ACCUMULATING** - накапливаем фрагменты
2. **READY** - есть готовые предложения для вывода  
3. **TIMEOUT** - принудительный вывод по таймауту

#### Критерии готовности предложения:
1. **Семантическая завершенность** - законченная мысль
2. **Естественная пауза** - логический переход к новой теме
3. **Достаточная длина** - минимум 8-12 слов
4. **Таймаут** - максимум 15 секунд накопления

### Пример работы системы:

#### Входные фрагменты:
```
Фрагмент 1: "произойти сигналом добродетели"
Фрагмент 2: "нападая на всё предприятие" 
Фрагмент 3: "говоря что зарабатывание денег это зло"
Фрагмент 4: "и вам не следует этого делать"
```

#### Анализ накопителя:
```
Накоплено: "произойти сигналом добродетели нападая на всё предприятие говоря что зарабатывание денег это зло и вам не следует этого делать"

Анализ: Завершенная мысль - критика через добродетельный сигналинг
Решение: READY_SENTENCES
```

#### Вывод форматировщика:
```
"Произойти может сигналом добродетели, нападая на всё предприятие, говоря что зарабатывание денег — это зло и вам не следует этого делать."
```

## Преимущества предлагаемого решения

### 1. Сохранение скорости
- Основной pipeline остается быстрым
- Накопление происходит параллельно
- Минимальная дополнительная задержка

### 2. Качество предложений
- Семантически завершенные предложения
- Естественная пунктуация и капитализация
- Сохранение смысла и потока речи

### 3. Гибкость системы
- Адаптация к разным стилям речи
- Настраиваемые параметры накопления
- Fallback на таймаут для гарантии вывода

### 4. Совместимость
- Не нарушает существующий pipeline
- Легко отключается для тестирования
- Сохраняет все текущие функции

## Настройки для оптимизации

### Параметры накопителя:
```yaml
sentence_accumulator:
  max_buffer_fragments: 10        # Максимум фрагментов в буфере
  min_sentence_words: 8           # Минимум слов в предложении
  accumulation_timeout: 15        # Таймаут накопления (секунды)
  semantic_completeness_threshold: 0.8  # Порог семантической завершенности
```

### Критерии качества:
- **Задержка**: < 3 секунд для 90% предложений
- **Завершенность**: > 95% семантически полных предложений  
- **Естественность**: Субъективная оценка носителей языка
- **Точность**: Сохранение исходного смысла

Это решение позволит получать качественные, завершенные предложения при сохранении преимуществ потоковой обработки.