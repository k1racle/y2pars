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

        # Ждем появления списка результатов
        await asyncio.sleep(3)
        
        # Пробуем разные селекторы для контейнера списка
        list_selectors = [
            'div[class*="business-list-view"]',
            'div[class*="search-results"]', 
            'div[class*="geo-search-list"]',
            'div[data-testing="search-results"]',
            'section[class*="search-results"]'
        ]
        
        list_container = None
        for selector in list_selectors:
            try:
                list_container = await page.wait_for_selector(selector, timeout=5000, state='visible')
                logger.info(f"  [Парсинг] Контейнер списка найден: {selector}")
                break
            except:
                continue
        
        if not list_container:
            logger.warning("  [Парсинг] Не удалось найти контейнер списка стандартными методами. Пробуем искать карточки напрямую...")
        
        # Селекторы для элементов списка (карточек)
        card_selectors = [
            'div[class*="business-list-view__list-item"]',
            'a[class*="business-card-link"]',
            'div[class*="search-snippet"]',
            'div[class*="geo-search-item"]',
            'article[class*="search-result"]',
            'div[class*="ymaps-biz-card"]'
        ]
        
        cards = []
        for selector in card_selectors:
            try:
                cards = await page.query_selector_all(selector)
                if cards:
                    logger.info(f"  [Парсинг] Найдено карточек по селектору '{selector}': {len(cards)}")
                    break
            except Exception as e:
                continue
        
        if not cards:
            # Если ничего не найдено, пробуем найти все div внутри потенциального контейнера
            logger.warning("  [Парсинг] Стандартные селекторы не сработали. Пробуем универсальный поиск...")
            if list_container:
                cards = await list_container.query_selector_all('div[class*="card"], article, div[class*="item"], div[class*="snippet"]')
            else:
                # Ищем любые элементы с текстом, похожие на названия организаций
                cards = await page.query_selector_all('div[class*="business"], div[class*="search"]')
            logger.info(f"  [Парсинг] Универсальным поиском найдено элементов: {len(cards)}")

        if not cards:
            logger.error("  [Парсинг] Не найдено никаких элементов списка. Возможно, результаты еще не загрузились или структура изменилась.")
            # Делаем скриншот для отладки
            await page.screenshot(path="debug_yandex_list.png", full_page=True)
            logger.info("  [Парсинг] Скриншот сохранен как debug_yandex_list.png")
            return []

        scroll_pause = 1.5
        no_progress_count = 0
        processed_count = 0
        
        while len(items) < max_items and no_progress_count < 3:
            # Обновляем список карточек после скролла
            current_cards = []
            for selector in card_selectors:
                try:
                    current_cards = await page.query_selector_all(selector)
                    if current_cards:
                        break
                except:
                    continue
            
            if not current_cards and cards:
                current_cards = cards  # Используем предыдущий список если новый не найден
            
            if not current_cards:
                logger.warning("  [Парсинг] Карточки пропали из DOM. Завершаем.")
                break

            logger.debug(f"  [Парсинг] Видимо карточек: {len(current_cards)}. Всего собрано: {len(items)}")

            for card in current_cards:
                if len(items) >= max_items:
                    break
                
                # Проверяем, видима ли карточка
                is_visible = await card.is_visible()
                if not is_visible:
                    continue
                    
                text_content = await card.inner_text()
                if len(text_content.strip()) < 5:
                    continue

                try:
                    # Название - ищем в разных местах
                    name = ""
                    name_selectors = [
                        'span[class*="business-card-header__title"]',
                        'span[class*="business-name"]',
                        'a[class*="business-card-link"] span',
                        'h2', 'h3', 'div[class*="title"]'
                    ]
                    for ns in name_selectors:
                        name_el = await card.query_selector(ns)
                        if name_el:
                            name = await name_el.inner_text()
                            if name:
                                break
                    
                    if not name:
                        # Если не нашли в селекторах, берем первую строку текста
                        lines = text_content.split('\n')
                        name = lines[0].strip() if lines else "Без названия"
                    
                    if len(name) > 100:  # Слишком длинное название - скорее всего мусор
                        continue

                    # Адрес
                    address = ""
                    addr_selectors = [
                        'span[class*="business-card-address"]',
                        'span[class*="address"]',
                        'div[class*="address"]',
                        'span[class*="geo-text"]'
                    ]
                    for ads in addr_selectors:
                        addr_el = await card.query_selector(ads)
                        if addr_el:
                            address = await addr_el.inner_text()
                            if address:
                                break

                    # Рейтинг
                    rating = ""
                    rating_selectors = [
                        'span[class*="business-rating__value"]',
                        'span[class*="rating-value"]',
                        'div[class*="rating"] span'
                    ]
                    for rs in rating_selectors:
                        rating_el = await card.query_selector(rs)
                        if rating_el:
                            rating = await rating_el.inner_text()
                            if rating:
                                break

                    # Ссылка
                    link = ""
                    link_el = await card.query_selector('a[class*="business-card-link"], a[href*="/maps/"]')
                    if link_el:
                        link = await link_el.get_attribute('href')
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
                    
                    if not is_duplicate and name != "Без названия":
                        items.append(item)
                        logger.debug(f"    + Добавлено: {name}")
                        processed_count += 1
                
                except Exception as e:
                    logger.error(f"  [Ошибка] При парсинге карточки: {e}")
                    continue

            if len(items) >= max_items:
                break

            # Скроллим вниз список
            logger.debug("  [Скролл] Прокручиваем список организаций...")
            
            # Пытаемся скроллить контейнер списка
            scrolled = False
            for scroll_selector in ['div[class*="scrollable-pane"]', 'div[class*="business-list-view"]', 'div[class*="search-results"]']:
                scroll_container = await page.query_selector(scroll_selector)
                if scroll_container:
                    await self.human.scroll_element(page, scroll_container, direction='down', amount=400)
                    scrolled = True
                    break
            
            if not scrolled:
                # Скроллим страницу
                await self.human.scroll_page(page, direction='down', pixels=400)

            await asyncio.sleep(scroll_pause)
            
            # Проверяем, появились ли новые элементы
            if len(items) == processed_count and processed_count > 0:
                no_progress_count += 1
            else:
                no_progress_count = 0
                processed_count = len(items)
            
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
