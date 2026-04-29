"""
Парсер Яндекс Карт - исправленная версия
"""
import asyncio
import logging
from typing import List, Dict
from playwright.async_api import Page, BrowserContext

try:
    from .human_behavior import HumanBehaviorSimulator
except ImportError:
    from human_behavior import HumanBehaviorSimulator

logger = logging.getLogger(__name__)

class YandexMapsParser:
    """Парсер для Яндекс Карт"""

    def __init__(self, context: BrowserContext, config: dict):
        self.context = context
        self.config = config
        self.human = HumanBehaviorSimulator(config)
        self.base_url = "https://yandex.ru/maps"

    async def search(self, page: Page, query: str, city: str):
        """Выполнение поиска через поле ввода на главной странице карт"""
        logger.info(f"  [Поиск] Переход на главную страницу Яндекс Карт")
        
        # Переходим на главную страницу карт
        await page.goto("https://yandex.ru/maps", wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)  # Ждем прогрузки интерфейса

        logger.info("  [Поиск] Поиск поля ввода...")
        try:
            # Ждем появления поля поиска
            search_box = await page.wait_for_selector(
                'input[data-testid="search-input"]', 
                state='visible',
                timeout=15000
            )
            logger.info("  [Поиск] Поле ввода найдено.")
            
            # Очищаем поле
            await search_box.fill("")
            await asyncio.sleep(0.5)
            
            # Вводим город и запрос
            search_text = f"{city} {query}"
            logger.info(f"  [Поиск] Ввод запроса: '{search_text}'")
            await self.human.type_text(page, 'input[data-testid="search-input"]', search_text)
            
            # Нажимаем Enter
            await search_box.press("Enter")
            logger.info("  [Поиск] Запрос отправлен (Enter).")
            
            # Ждем появления результатов
            await asyncio.sleep(5) 
            
        except Exception as e:
            logger.error(f"  [Ошибка] Не удалось найти поле поиска или ввести текст: {e}")
            # Пробуем альтернативный селектор
            try:
                alt_box = await page.wait_for_selector('input[class*="search-input"]', timeout=5000)
                await alt_box.fill(f"{city} {query}")
                await alt_box.press("Enter")
                await asyncio.sleep(5)
            except:
                raise Exception("Не удалось взаимодействовать с поиском Яндекса")

    async def parse_cards(self, page: Page, max_items: int) -> List[Dict]:
        """Собирает данные из списка организаций"""
        items = []
        logger.info("  [Парсинг] Начинаем сбор данных из списка...")

        # Селекторы для элементов списка
        list_item_selector = 'div[class*="business-list-view__list-item"]'
        
        scroll_pause = 1.5
        no_progress_count = 0
        
        while len(items) < max_items and no_progress_count < 3:
            # Находим все видимые карточки в списке
            cards = await page.query_selector_all(list_item_selector)
            
            if not cards:
                logger.warning("  [Парсинг] Карточки не найдены. Пробуем альтернативные селекторы...")
                cards = await page.query_selector_all('a[class*="business-card-link"]')
                if not cards:
                    break

            logger.debug(f"  [Парсинг] Найдено элементов в списке: {len(cards)}. Всего собрано: {len(items)}")

            for card in cards:
                if len(items) >= max_items:
                    break
                
                text_content = await card.inner_text()
                if len(text_content.strip()) < 5:
                    continue

                try:
                    # Название
                    name_el = await card.query_selector('span[class*="business-card-header__title"]')
                    name = await name_el.inner_text() if name_el else "Без названия"

                    # Адрес
                    addr_el = await card.query_selector('span[class*="business-card-address"]')
                    address = await addr_el.inner_text() if addr_el else ""

                    # Рейтинг
                    rating_el = await card.query_selector('span[class*="business-rating__value"]')
                    rating = await rating_el.inner_text() if rating_el else ""

                    # Ссылка
                    link_el = await card.query_selector('a[class*="business-card-link"]')
                    link = await link_el.get_attribute('href') if link_el else ""
                    if link and link.startswith('/'):
                        link = f"https://yandex.ru{link}"

                    item = {
                        'source': 'Yandex Maps',
                        'name': name,
                        'address': address,
                        'rating': rating,
                        'url': link,
                    }
                    
                    # Проверка на дубликаты
                    is_duplicate = any(
                        i['name'] == name and i['address'] == address 
                        for i in items
                    )
                    
                    if not is_duplicate:
                        items.append(item)
                        logger.debug(f"    + Добавлено: {name}")
                
                except Exception as e:
                    logger.error(f"  [Ошибка] При парсинге карточки: {e}")
                    continue

            if len(items) >= max_items:
                break

            # Скроллим вниз список
            logger.debug("  [Скролл] Прокручиваем список организаций...")
            list_container = await page.query_selector('div[class*="scrollable-pane"]')
            if list_container:
                await self.human.scroll_element(page, list_container, direction='down', amount=400)
            else:
                await self.human.scroll_page(page, direction='down', pixels=400)

            await asyncio.sleep(scroll_pause)
            no_progress_count += 1
            
        logger.info(f"  [Итого] Собрано объектов: {len(items)}")
        return items

    async def parse_city_query(self, city: str, query: str, max_items: int = 50) -> List[Dict]:
        """Основной метод парсинга для одного запроса в городе"""
        logger.info(f"Парсинг Яндекс Карт: {city} | Запрос: {query}")
        
        page = await self.context.new_page()
        try:
            # 1. Поиск
            await self.search(page, query, city)
            
            # 2. Парсинг
            items = await self.parse_cards(page, max_items)
            
            return items
            
        except Exception as e:
            logger.error(f"Критическая ошибка при парсинге {city} ({query}): {e}")
            await page.screenshot(path=f"error_yandex_{city}_{query}.png")
            logger.error(f"Скриншот ошибки сохранен: error_yandex_{city}_{query}.png")
            return []
        finally:
            await page.close()
