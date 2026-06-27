# RLM — Remote Sensing & Monitoring Toolkit

**Версия:** 0.2.0

## Цель проекта

**RLM** — это инструмент для агрономов, который позволяет:
- Просматривать спутниковые снимки участков полей и маршрутов в разные периоды времени.
- Работать с разными спектрами и индексами: **True Color (видимый)**, **False Color (инфракрасный)**, **NDVI**, **NDWI**, **EVI** и другими.
- Получать профессиональный анализ и рекомендации с помощью **LLM (Qwen3 via OpenRouter)**.
- Прогнозировать урожайность на основе исторических спутниковых данных (пилотный ML-модуль).

Основной сценарий использования:
Пользователь загружает файл `.kml` с границами поля → система находит и показывает доступные чистые (малооблачные) спутниковые снимки Sentinel-2 → пользователь выбирает дату и тип визуализации → на экране отображается фрагмент снимка с наложенным контуром поля.

---

## Текущее состояние (обновлённое)

### Основная бизнес-задача

Создать удобный инструмент, который позволяет агроному **визуально анализировать** состояние поля в динамике по спутниковым данным.

### Конкретные шаги работы пользователя

1. **Определение буферной зоны**
   - Пользователь указывает файл `field.kml` (или GeoJSON).
   - Система автоматически создаёт буфер **500 метров наружу** от границы поля (параметр `buffer_meters` вынесен в настройки/CLI/аргументы).
   - Поиск снимков ведётся по этой расширенной области.

2. **Поиск доступных снимков**
   - Найти все доступные сцены **Sentinel-2 Level-2A** за выбранный период через **STAC API (Earth Search by Element 84)**.
   - Дополнительно: прямой поиск COG-файлов через **Dagshub S3** (устаревающий метод).
   - Отфильтровать по облачности (cloud cover ≤ 20–30%).
   - Показать пользователю список доступных дат, % облачности и preview.

3. **Выбор и визуализация**
   - Пользователь выбирает одну или несколько дат.
   - Выбирает тип продукта:
     - True Color (RGB)
     - False Color (NIR + Red + Green)
     - NDVI
     - NDWI
     - NDVI + контур поля (overlay)
   - Система вырезает фрагмент снимка по буферной зоне, накладывает контур поля и отображает результат.

4. **Дополнительно (LLM-анализ)**
   - После визуализации можно отправить полученные индексы и изображение (или описание) на анализ в **Qwen3** с запросом агрономических рекомендаций.

5. **Прогнозирование урожайности (пилот)**
   - На основе исторических данных NDVI и урожайности строится модель прогноза (нейросеть).
   - Детали: см. `docs/presCropYieldPrediction.md`.

---

## Структура проекта

```
YieldPrediction/
├── docs/
│   ├── README.md                  ← этот файл
│   ├── ARCHITECTURE.md            # Архитектура системы
│   ├── DEVELOPMENT_PLAN.md        # План разработки
│   └── presCropYieldPrediction.md # Прогнозирование урожайности (пилот)
│
├── src/
│   ├── rlm/                        # Основной пакет RLM
│   │   ├── __init__.py             # Версия 0.2.0
│   │   ├── config.py               # Настройки (PydanticSettings, .env)
│   │   ├── models.py               # Pydantic-модели данных
│   │   ├── cli.py                  # CLI-интерфейс (typer)
│   │   ├── server.py               # MCP-сервер (FastMCP)
│   │   ├── search.py               # Поиск сцен: STAC API + буфер
│   │   ├── dagshub_search.py       # Поиск сцен через Dagshub S3
│   │   ├── processor.py            # Оркестратор: буфер → поиск → индексы → отчёт
│   │   ├── indices.py              # Расчёт NDVI, NDWI + визуализация (RGB, contour)
│   │   ├── downloader.py           # Скачивание Sentinel-данных
│   │   ├── sentinel_filter.py      # Двухэтапная фильтрация: STAC + SCL mask
│   │   └── llm.py                  # Обёртка LiteLLM + OpenRouter (Qwen3)
│   │
│   ├── input/                      # Входные данные (KML и пр.)
│   ├── ReadKmlAndFindTheData.py    # Утилиты (легаси)
│   ├── ReadSentinel.py
│   ├── field_ndvi_v1.py / v2.py
│   └── ...
│
├── tests/
│   ├── test_e2e_rlm.py             # E2E-тесты
│   ├── test_processor.py           # Тесты processor/indices
│   ├── test_e2e_2025_one_per_month.py # E2E: фильтрация по месяцам 2025
│   └── fixtures/                   # Тестовые данные
│
├── data/
│   └── demo_S2A_20250515/          # Демо-сцена Sentinel-2
│
├── debug_filter.py                 # Отладочный скрипт фильтрации
└── pyproject.toml                  # Зависимости, entry-points
```

---

## Технические требования

### Входные данные
- KML / GeoJSON файл с геометрией поля (Polygon или LineString).
- Параметры: `buffer_meters` (по умолчанию 500), период дат, максимальная облачность.

### Выходные данные
- Список доступных сцен с метаданными.
- Растровые изображения (PNG/TIFF) с наложенным контуром поля:
  - RGB (True Color)
  - NDVI + contour overlay
- Опционально: JSON-отчёт + текстовый анализ от LLM.

### Используемые технологии
- **Sentinel-2** — STAC API (Earth Search by Element 84, pystac-client), Dagshub S3.
- `rasterio`, `rioxarray`, `geopandas`, `shapely`, `pystac-client`.
- `matplotlib` для визуализации (RGB, NDVI, overlay).
- `litellm` + **OpenRouter** (модель `qwen/qwen3-70b`).
- **MCP** (Model Context Protocol) — интеграция с AI-агентами (Claude, Cursor, Windsurf и др.).
- `typer` для CLI, `pydantic-settings` для конфигурации.

### Архитектура (текущая)

```
docs/
src/rlm/
├── cli.py                 # Командная строка (typer)
├── server.py              # MCP сервер (FastMCP)
├── llm.py                 # Работа с Qwen3 через LiteLLM
├── config.py              # Pydantic-settings конфигурация
├── models.py              # Pydantic модели данных
├── search.py              # Поиск сцен через STAC API + буфер
├── dagshub_search.py      # Поиск сцен через Dagshub S3 (legacy)
├── processor.py           # Оркестратор обработки поля
├── indices.py             # Расчёт индексов и визуализация
├── downloader.py          # Скачивание Sentinel-данных
├── sentinel_filter.py     # Двухэтапная фильтрация: STAC + SCL mask (COG)
```

---

## Статус реализации

### ✅ Завершено
- [x] Документация: README, ARCHITECTURE, DEVELOPMENT_PLAN
- [x] Конфигурация через `.env` + `pydantic-settings`
- [x] Pydantic-модели (SearchRequest, SceneMetadata, AnalysisResult)
- [x] CLI-интерфейс (поиск, анализ)
- [x] MCP-сервер (инструменты: `list_available_scenes`, `analyze_field`)
- [x] Создание буферной зоны 500м (shapely + geopandas)
- [x] Поиск сцен через STAC API (pystac-client, Earth Search)
- [x] Расчёт NDVI, NDWI
- [x] Визуализация: RGB + NDVI + contour overlay
- [x] Обработка облачности (SCL mask)
- [x] Интеграция с Qwen3 через LiteLLM + OpenRouter
- [x] Многосценовая обработка
- [x] Двухэтапная SCL-фильтрация (STAC pre-filter + полевая проверка по SCL)
- [x] E2E-тесты: фильтрация по месяцам 2025

### 🚧 В разработке / Планируется
- [ ] Полноценный веб-интерфейс (Streamlit / Gradio)
- [ ] Таймлапс-сравнение дат
- [ ] Автоматическое выделение проблемных зон на полях
- [ ] Модель прогноза урожайности (ML)
- [ ] Docker-образ

---

## Быстрый старт

```bash
# Установка
pip install -e .

# Настройка
cp .env.example .env
# Отредактируйте .env: укажите OPENROUTER_API_KEY

# Поиск сцен
rlm search tests/fixtures/test_field.kml

# Полный анализ поля
rlm analyze tests/fixtures/test_field.kml

# Двухэтапная SCL-фильтрация снимков (STAC + SCL маска)
python tests/test_e2e_2025_one_per_month.py

# MCP-сервер (для AI-агентов)
rlm-mcp
```

---

## Дополнительные документы

- [Архитектура системы](ARCHITECTURE.md)
- [План разработки](DEVELOPMENT_PLAN.md)
- [Прогнозирование урожайности (пилот)](presCropYieldPrediction.md)