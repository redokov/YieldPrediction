# Архитектура RLM (RLM Architecture)

**Версия документа:** 1.1 (актуализирован 2026-06-26)

## 1. Общее описание

**RLM (Remote Sensing & Monitoring)** — модульная система для поиска, обработки и анализа спутниковых данных Sentinel-2 с фокусом на агрономические задачи.  
Система позволяет получать снимки полей с буферной зоной, рассчитывать спектральные индексы (NDVI, NDWI) и получать экспертные рекомендации через LLM (Qwen3 via OpenRouter).

Архитектура спроектирована как **лёгкий, расширяемый Python-пакет** с сильной интеграцией через **MCP** (Model Context Protocol).

---

## 2. Цели архитектуры

- Чёткое разделение ответственности (Separation of Concerns)
- Лёгкая интеграция с AI-агентами через MCP
- Минимальные зависимости при быстром поиске и фильтрации сцен через STAC API
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
    
    D --> G["STAC API (Earth Search by Element 84)"]
    D --> H["Dagshub S3 (legacy)"]
    E --> I[Geospatial Processor\n(geopandas, shapely, rasterio)]
    E --> J[Index Calculator\n(NDVI, NDWI, SCL mask)]
    F --> K[LiteLLM + OpenRouter\n(Qwen3-70B)]
    
    E --> L[Output: Report + Images (RGB, NDVI)]
    F --> L
```

---

## 4. Структура проекта (фактическая)

```
docs/
├── README.md
├── DEVELOPMENT_PLAN.md
├── ARCHITECTURE.md          ← текущий документ
└── presCropYieldPrediction.md

src/rlm/
├── __init__.py                # Версия 0.2.0, импорт публичных API
├── config.py                  # PydanticSettings: buffer_meters, max_cloud_cover, даты, API-ключи
├── models.py                  # Pydantic-модели: FieldBoundary, SceneMetadata, SearchRequest, AnalysisResult
├── cli.py                     # CLI-интерфейс (typer): команды search, analyze
├── server.py                  # MCP-сервер (FastMCP): инструменты list_available_scenes, analyze_field
├── search.py                  # Поиск сцен через STAC API (pystac-client) + create_buffer()
├── dagshub_search.py          # Поиск сцен через Dagshub S3 (устаревающий, для fallback)
├── processor.py               # Оркестратор: create_buffer → list_scenes → process_scene_indices → отчёт
├── indices.py                 # Расчёт NDVI/NDWI + визуализация RGB/NDVI с контуром поля
├── downloader.py              # Скачивание/доступ к COG-файлам Sentinel-2 L2A
├── sentinel_filter.py         # Двухэтапная SCL-фильтрация (STAC + SCL mask)
├── llm.py                     # Обёртка LiteLLM + OpenRouter (Qwen3-70B)
└── server.py                  # MCP сервер (инструменты list_available_scenes, analyze_field)
```

### Ключевые модули и их ответственность

| Модуль               | Ответственность |
|----------------------|-----------------|
| `config.py`          | Загрузка `.env`, параметры по умолчанию (buffer_meters=500, max_cloud_cover=30 и т.д.) |
| `models.py`          | Строго типизированные модели: `FieldBoundary`, `SceneMetadata`, `SearchRequest`, `AnalysisResult` |
| `search.py`          | Поиск сцен Sentinel-2 через STAC API (Earth Search by Element 84), фильтрация по дате, облачности, Level-2A. Возвращает список `SceneMetadata`. Также содержит `create_buffer()` |
| `dagshub_search.py`  | Альтернативный поиск сцен через прямые COG-файлы на S3 (Dagshub bucket). MGRS-based |
| `processor.py`       | **Оркестратор бизнес-логики**:<br>• Создание буфера 500 м<br>• Поиск сцен (STAC + fallback на демо)<br>• Запуск расчёта индексов<br>• Формирование отчёта<br>• Многосценовая обработка (`process_multiple_scenes`) |
| `indices.py`         | Расчёт NDVI, NDWI, визуализация RGB + NDVI с наложением контура поля |
| `sentinel_filter.py` | Двухэтапная фильтрация: 1) STAC pre-filter, 2) SCL-проверка по полю (COG). `filter_pipeline()`, `run()` |
| `llm.py`             | Взаимодействие с Qwen3 через LiteLLM. Поддержка `call_llm()` |
| `server.py`          | Реализация MCP-инструментов (`list_available_scenes`, `analyze_field`) |
| `cli.py`             | Удобный интерфейс командной строки (команды `search`, `analyze`) |

---

## 5. Поток выполнения основного сценария

1. Пользователь вызывает `rlm analyze field.kml` (через CLI) или `analyze_field("field.kml")` (через MCP).
2. `processor.process_scene()` — точка входа:
   - **Шаг 1:** `search.create_buffer()` — создаёт внешнюю зону 500 метров (GeoJSON).
   - **Шаг 2:** `processor.list_scenes()` — поиск сцен через STAC API + fallback на Dagshub S3.
   - **Шаг 3:** Выбор лучшей сцены (минимальная облачность).
   - **Шаг 4:** `indices.process_scene_indices()` — загрузка COG-бэндов (TCI, B04, B08), расчёт NDVI/NDWI, маска облачности, визуализация RGB + NDVI с контуром.
3. Формируется текстовый отчёт с метриками.
4. (Опционально) `llm.call_llm()` — отправка отчёта в Qwen3 для агрономических рекомендаций.
5. Возвращается `AnalysisResult` со статусом, отчётом и LLM-анализом.

### Многосценовый режим

Функция `process_multiple_scenes()` реализует пакетную обработку:
1. Поиск всех доступных сцен за период.
2. Выбор первых N сцен (по умолчанию 5).
3. Для каждой — расчёт индексов и визуализация.
4. Возврат списка результатов.

---

## 6. Технические решения и библиотеки

- **Геометрия и буфер**: `shapely` + `geopandas` (буфер в метрах с `to_crs` в UTM)
- **Каталог Sentinel-2**: `pystac-client` → Earth Search (Element 84). Legacy: `sentinelsat`, Dagshub S3
- **Обработка растра**: `rasterio`, `rioxarray`, `numpy`
- **Облачная маска**: SCL band (Level-2A) через `sentinel_filter.py`
- **LLM**: `litellm` → OpenRouter → `qwen/qwen3-70b`
- **MCP**: `mcp.server.fastmcp.FastMCP`
- **CLI**: `typer`
- **Конфигурация**: `pydantic-settings`

---

## 7. Решения по отложенным частям

- Полноценный `visualizer.py` (matplotlib, folium, легенды) — отложен. Визуализация встроена в `indices.py` (минимальная: сохранение PNG с помощью `matplotlib` + наложение контура через `geopandas`).
- Веб-интерфейс (Streamlit/Gradio) — в планах.

---

## 8. Расширяемость

- Легко добавить другие спутники (Landsat, Sentinel-1) — новый провайдер в `search.py`.
- Возможность подключения собственных ML-моделей прогноза урожайности (см. `docs/presCropYieldPrediction.md`).
- Поддержка нескольких форматов входных данных (KML, GeoJSON, Shapefile) — уже реализована через `geopandas`.
- Добавление новых вегетационных индексов: расширение `indices.py`.

---

**Дата создания:** 2026-06-26  
**Статус:** Актуализирован под версию кода 0.2.0