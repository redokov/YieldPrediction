# Архитектура RLM (RLM Architecture)

## 1. Общее описание

**RLM (Remote Learning & Monitoring)** — модульная система для поиска, обработки и анализа спутниковых данных Sentinel-2 с фокусом на агрономические задачи.  
Система позволяет получать снимки полей с буферной зоной, рассчитывать спектральные индексы и получать экспертные рекомендации через LLM (Qwen3 via OpenRouter).

Архитектура спроектирована как **лёгкий, расширяемый Python-пакет** с сильной интеграцией через **MCP** (Model Context Protocol).

---

## 2. Цели архитектуры

- Чёткое разделение ответственности (Separation of Concerns)
- Лёгкая интеграция с AI-агентами через MCP
- Минимальные зависимости при быстром поиске и фильтрации сцен
- Возможность постепенного добавления визуализации и ML-моделей
- Поддержка как CLI, так и серверного (MCP) режима работы

---

## 3. Высокоуровневая архитектура

```mermaid
graph TD
    A[Пользователь / AI Agent] --> B[MCP Server / CLI]
    B --> C[Config & Settings]
    B --> D[Search Service]
    B --> E[Processor Service]
    B --> F[LLM Service]
    
    D --> G[ Sentinel-2 Catalog\n(sentinelsat / planetary-computer) ]
    E --> H[Geospatial Processor\n(geopandas, shapely, rasterio)]
    E --> I[Index Calculator\n(NDVI, NDWI, SCL mask)]
    F --> J[LiteLLM + OpenRouter\n(Qwen3-70B)]
    
    E --> K[Output: Report + Images]
    F --> K
```

---

## 4. Структура проекта

```
docs/
├── README.md
├── DEVELOPMENT_PLAN.md
├── ARCHITECTURE.md          ← текущий документ
├── API.md
└── USER_STORIES.md

src/rlm/
├── __init__.py
├── config.py                # Настройки, PydanticSettings
├── models.py                # Pydantic-модели (Scene, Field, Request, Response)
├── cli.py                   # Командная строка (typer/click)
├── server.py                # MCP сервер + инструменты
├── llm.py                   # Обёртка над LiteLLM + Qwen3
├── search.py                # Поиск сцен (catalog query)
├── processor.py             # Буфер, вырезка, маски, индексы
├── visualizer.py            # (минимальная версия — отложена)
├── utils.py
└── exceptions.py
```

### Ключевые модули и их ответственность

| Модуль            | Ответственность |
|-------------------|-----------------|
| `config.py`       | Загрузка `.env`, параметры по умолчанию (buffer_meters=500, max_cloud_cover=30 и т.д.) |
| `models.py`       | Строго типизированные модели: `FieldBoundary`, `SceneMetadata`, `VisualizationRequest`, `LLMAnalysis` |
| `search.py`       | Поиск сцен Sentinel-2, фильтрация по дате, облачности, Level-2A. Возвращает список `SceneMetadata` |
| `processor.py`    | **Основная бизнес-логика**:<br>• Создание буфера 500 м<br>• Скачивание/доступ к сцене<br>• Вырезка по bounding box<br>• Расчёт индексов<br>• Применение облачной маски (SCL) |
| `llm.py`          | Взаимодействие с Qwen3. Поддержка `analyze_scene()` — анализ индексов + текстового описания снимка |
| `server.py`       | Реализация MCP-инструментов (`list_scenes`, `analyze_field`, `ask_agronomist` и др.) |
| `cli.py`          | Удобный интерфейс командной строки |

---

## 5. Поток выполнения основного сценария

1. Пользователь вызывает `analyze_field("field.kml")` (через MCP или CLI).
2. `processor.create_buffer()` — создаёт внешнюю зону 500 метров.
3. `search.list_scenes()` — возвращает список доступных чистых сцен.
4. Пользователь (или агент) выбирает сцену.
5. `processor.process_scene()`:
   - Загружает нужные бэнды
   - Вырезает по буферу
   - Применяет SCL-маску
   - Считает NDVI, NDWI и другие индексы
6. `llm.analyze()` — отправляет сводку по индексам + метаданные в Qwen3.
7. Возвращается структурированный отчёт + (позже) путь к сгенерированному изображению.

---

## 6. Технические решения и библиотеки

- **Геометрия и буфер**: `shapely` + `geopandas` (буфер в метрах с `to_crs` в UTM)
- **Каталог Sentinel-2**: Сначала `sentinelsat`, в дальнейшем переход на `planetary-computer` или `sentinelhub-py` (COG, быстрее)
- **Обработка растра**: `rasterio`, `rioxarray`, `numpy`
- **Облачная маска**: SCL band (Level-2A)
- **LLM**: `litellm` → OpenRouter → `qwen/qwen3-70b`
- **MCP**: `mcp.server.fastmcp.FastMCP`
- **CLI**: `typer` (рекомендуется) или `click`
- **Конфигурация**: `pydantic-settings`

---

## 7. Решения по отложенным частям

- Полноценный `visualizer.py` (matplotlib, folium, легенды) — отложен до следующей итерации.
- В текущей версии визуализация будет минимальной: сохранение PNG с помощью `rasterio.plot` + наложение контура через `geopandas`.
- Веб-интерфейс (Streamlit/Gradio) — Этап 4 (опционально).

---

## 8. Расширяемость

- Легко добавить другие спутники (Landsat, Sentinel-1).
- Возможность подключения собственных ML-моделей прогноза урожайности.
- Поддержка нескольких форматов входных данных (KML, GeoJSON, Shapefile).

---

**Дата создания:** {{current_date}}  
**Статус:** Утверждена вместе с `DEVELOPMENT_PLAN.md` (без отдельного большого Этапа 3).

---

Готовы ли вы начать реализацию кода по Этапу 1?

Если да — скажите **«Начинай Этап 1»**, и я:
1. Создам недостающие модули (`config.py`, `models.py`, `search.py`, `processor.py`).
2. Обновлю `server.py` и `cli.py`.
3. Реализую функцию создания буфера 500 метров и улучшенный поиск сцен.
