# Парсер Яндекс Карт и 2ГИС

Парсер для сбора данных об объектах (рестораны, кафе, магазины и т.д.) с Яндекс Карт и 2ГИС с экспортом в Excel.

## Особенности

- **Имитация человеческого поведения**: 
  - Плавные движения мыши по кривой Безье
  - Случайные задержки между действиями
  - Человеческая прокрутка с паузами и откатами назад
  - Посимвольный ввод текста с неравномерными задержками
  
- **Гибкая настройка**:
  - Выбор городов для парсинга
  - Настройка поисковых запросов
  - Приоритет источников (Яндекс/2ГИС)
  - Очередь выполнения
  
- **Экспорт в Excel**:
  - Автоматическое форматирование
  - Цветовое разделение источников
  - Фильтры и автоширина колонок

## Структура проекта

```
yandex_2gis_parser/
├── config/
│   └── settings.json      # Конфигурационный файл
├── output/                 # Папка для результатов
├── logs/                   # Логи работы
├── main.py                # Основной модуль
├── yandex_parser.py       # Парсер Яндекс Карт
├── gis2_parser.py         # Парсер 2ГИС
├── human_behavior.py      # Имитация человеческого поведения
└── excel_exporter.py      # Экспорт в Excel
```

## Установка

1. Установите зависимости:
```bash
pip install playwright openpyxl
playwright install chromium
```

2. Настройте `config/settings.json` под ваши нужды

## Конфигурация

Пример файла `settings.json`:

```json
{
  "cities": [
    {
      "name": "Москва",
      "priority": 1,
      "enabled": true,
      "search_queries": ["рестораны", "кафе", "кофейни"]
    },
    {
      "name": "Санкт-Петербург",
      "priority": 2,
      "enabled": true,
      "search_queries": ["рестораны", "кафе"]
    }
  ],
  "sources": {
    "yandex_maps": {
      "enabled": true,
      "priority": 1,
      "fields": ["name", "address", "rating", "reviews_count", "phone", "website", "category"]
    },
    "gis_2": {
      "enabled": true,
      "priority": 2,
      "fields": ["name", "address", "rating", "reviews_count", "phone", "website", "category", "hours"]
    }
  },
  "parsing_settings": {
    "max_objects_per_query": 50,
    "delay_between_actions_min": 2,
    "delay_between_actions_max": 5,
    "scroll_pause_min": 1,
    "scroll_pause_max": 3,
    "mouse_movement_enabled": true,
    "random_scroll_enabled": true,
    "headless_mode": false,
    "proxy_enabled": false,
    "proxy_list": []
  },
  "output": {
    "format": "xlsx",
    "filename_pattern": "{city}_{source}_{date}.xlsx",
    "save_path": "./output"
  }
}
```

## Использование

### Запуск парсера

```bash
cd yandex_2gis_parser
python main.py
```

### Программное использование

```python
import asyncio
from main import MapsParser

async def run_parser():
    parser = MapsParser('config/settings.json')
    
    # Запуск парсинга
    await parser.parse_all()
    
    # Экспорт результатов (combined=True - один файл, False - раздельные)
    parser.export_results(combined=True)
    
    # Статистика
    stats = parser.get_statistics()
    print(f"Всего объектов: {stats['total_objects']}")

asyncio.run(run_parser())
```

## Настройки имитации человека

В `settings.json` можно настроить:

- `delay_between_actions_min/max` - минимальная/максимальная задержка между действиями (сек)
- `scroll_pause_min/max` - пауза между скроллами (сек)
- `mouse_movement_enabled` - включить плавное движение мыши
- `random_scroll_enabled` - включить случайную прокрутку с откатами
- `headless_mode` - скрытый режим браузера (False для лучшей имитации)

## Собираемые данные

Для каждого объекта собираются:
- Название
- Адрес
- Рейтинг
- Количество отзывов
- Телефон
- Сайт
- Категория
- Часы работы (если доступно)
- Ссылка на объект
- Город
- Поисковый запрос
- Источник (yandex_maps/gis_2)

## Важные замечания

1. **Соблюдайте правила сервисов** - не устанавливайте слишком агрессивные настройки парсинга
2. **Используйте прокси** при большом объеме запросов
3. **Делайте перерывы** между сессиями парсинга
4. **Не используйте headless режим** для лучшей имитации человека

## Лицензия

Используйте на свой страх и риск. Соблюдайте условия использования Яндекс Карт и 2ГИС.
