"""
Основной модуль парсера Яндекс Карт и 2ГИС
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright, BrowserContext

from .yandex_parser import YandexMapsParser
from .gis2_parser import Gis2Parser
from .excel_exporter import ExcelExporter
from .human_behavior import HumanBehaviorSimulator


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MapsParser:
    """Основной класс парсера для Яндекс Карт и 2ГИС"""
    
    def __init__(self, config_path: str = 'config/settings.json'):
        self.config = self._load_config(config_path)
        self.exporter = ExcelExporter(self.config)
        self.all_data = {}
        
    def _load_config(self, config_path: str) -> dict:
        """Загрузка конфигурации из JSON файла"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Файл конфигурации {config_path} не найден. Используются настройки по умолчанию.")
            return self._default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка parsing JSON: {e}")
            return self._default_config()
            
    def _default_config(self) -> dict:
        """Конфигурация по умолчанию"""
        return {
            "cities": [
                {
                    "name": "Москва",
                    "priority": 1,
                    "enabled": True,
                    "search_queries": ["рестораны", "кафе"]
                }
            ],
            "sources": {
                "yandex_maps": {"enabled": True, "priority": 1},
                "gis_2": {"enabled": True, "priority": 2}
            },
            "parsing_settings": {
                "max_objects_per_query": 50,
                "delay_between_actions_min": 2,
                "delay_between_actions_max": 5,
                "scroll_pause_min": 1,
                "scroll_pause_max": 3,
                "mouse_movement_enabled": True,
                "random_scroll_enabled": True,
                "headless_mode": False
            },
            "output": {
                "format": "xlsx",
                "filename_pattern": "{city}_{source}_{date}.xlsx",
                "save_path": "./output"
            }
        }
        
    async def parse_all(self):
        """Запуск парсинга по всем городам и источникам"""
        logger.info("=== Запуск парсера ===")
        
        # Получаем активные города сортированные по приоритету
        cities = [c for c in self.config['cities'] if c.get('enabled', True)]
        cities.sort(key=lambda x: x.get('priority', 999))
        
        # Получаем активные источники
        sources = self.config['sources']
        
        async with async_playwright() as p:
            # Запускаем браузер
            browser = await p.chromium.launch(
                headless=self.config['parsing_settings'].get('headless_mode', False),
                slow_mo=100  # Замедление для имитации человека
            )
            
            # Создаем контекст с настройками
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="ru-RU",
                timezone_id="Europe/Moscow"
            )
            
            try:
                for city in cities:
                    city_name = city['name']
                    logger.info(f"\n=== Обработка города: {city_name} ===")
                    
                    self.all_data[city_name] = {}
                    
                    queries = city.get('search_queries', ['рестораны'])
                    max_items = self.config['parsing_settings'].get('max_objects_per_query', 50)
                    
                    # Парсим Яндекс Карты
                    if sources.get('yandex_maps', {}).get('enabled', True):
                        logger.info(f"Парсинг Яндекс Карт: {city_name}")
                        yandex_parser = YandexMapsParser(context, self.config)
                        
                        all_yandex_data = []
                        for query in queries:
                            logger.info(f"  Запрос: {query}")
                            items = await yandex_parser.parse_city_query(city_name, query, max_items)
                            all_yandex_data.extend(items)
                            logger.info(f"    Найдено объектов: {len(items)}")
                            
                            # Пауза между запросами
                            await asyncio.sleep(5)
                            
                        self.all_data[city_name]['yandex_maps'] = all_yandex_data
                        logger.info(f"  Всего из Яндекс Карт: {len(all_yandex_data)} объектов")
                    
                    # Парсим 2ГИС
                    if sources.get('gis_2', {}).get('enabled', True):
                        logger.info(f"Парсинг 2ГИС: {city_name}")
                        gis_parser = Gis2Parser(context, self.config)
                        
                        all_gis_data = []
                        for query in queries:
                            logger.info(f"  Запрос: {query}")
                            items = await gis_parser.parse_city_query(city_name, query, max_items)
                            all_gis_data.extend(items)
                            logger.info(f"    Найдено объектов: {len(items)}")
                            
                            # Пауза между запросами
                            await asyncio.sleep(5)
                            
                        self.all_data[city_name]['gis_2'] = all_gis_data
                        logger.info(f"  Всего из 2ГИС: {len(all_gis_data)} объектов")
                    
                    # Пауза между городами
                    await asyncio.sleep(10)
                    
            finally:
                await context.close()
                await browser.close()
                
        logger.info("\n=== Парсинг завершен ===")
        
    def export_results(self, combined: bool = True):
        """Экспорт результатов в Excel"""
        logger.info("Экспорт результатов...")
        
        if combined:
            # Объединяем все данные в один файл
            all_items = []
            for city_data in self.all_data.values():
                for source_items in city_data.values():
                    all_items.extend(source_items)
                    
            if all_items:
                filepath = self.exporter.export_all(all_items)
                logger.info(f"Общий файл сохранен: {filepath}")
        else:
            # Раздельные файлы по городам и источникам
            files = self.exporter.export_by_city_source(self.all_data)
            logger.info(f"Сохранено файлов: {len(files)}")
            for f in files:
                logger.info(f"  - {f}")
                
    def get_statistics(self) -> Dict:
        """Получение статистики по результатам парсинга"""
        stats = {
            'total_objects': 0,
            'by_city': {},
            'by_source': {}
        }
        
        for city, sources in self.all_data.items():
            city_total = 0
            stats['by_city'][city] = {}
            
            for source, items in sources.items():
                count = len(items)
                city_total += count
                stats['by_city'][city][source] = count
                
                if source not in stats['by_source']:
                    stats['by_source'][source] = 0
                stats['by_source'][source] += count
                
            stats['total_objects'] += city_total
            
        return stats


async def main():
    """Точка входа"""
    parser = MapsParser('config/settings.json')
    
    # Запуск парсинга
    await parser.parse_all()
    
    # Экспорт результатов
    parser.export_results(combined=True)
    
    # Вывод статистики
    stats = parser.get_statistics()
    print("\n=== Статистика ===")
    print(f"Всего объектов: {stats['total_objects']}")
    print("\nПо городам:")
    for city, sources in stats['by_city'].items():
        print(f"  {city}:")
        for source, count in sources.items():
            print(f"    {source}: {count}")
    print("\nПо источникам:")
    for source, count in stats['by_source'].items():
        print(f"  {source}: {count}")


if __name__ == '__main__':
    asyncio.run(main())
