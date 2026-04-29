"""
Парсер Яндекс Карт - исправленная версия
"""
import asyncio
import logging
from typing import List, Dict
from playwright.async_api import Page, BrowserContext

try:
    from .human_behavior import HumanBehavior
except ImportError:
    from human_behavior import HumanBehavior

logger = logging.getLogger(__name__)

class YandexMapsParser:
    """Парсер для Яндекс Карт"""

    def __init__(self, context: BrowserContext, config: dict):
        self.context = context
        self.config = config
        # Используем алиас HumanBehavior (который ссылается на HumanBehaviorSimulator)
        self.human = HumanBehavior(config)
        self.base_url = "https://yandex.ru/maps"

    async def search(self, page: Page, query: str, city: str):
        """Выполнение поиска через поле ввода на главной странице карт"""
        logger.info(f"  [Поиск] Переход на главную страницу Яндекс Карт")
        
        # Переходим на главную страницу карт
        await page.goto("https://yandex.ru/maps", wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)  # Ждем прогрузки интерфейса

        logger.info("  [Поиск] Поиск поля ввода...")
        try:
            # Ждем появления поля поиска по вашему селектору
            search_wrapper = await page.wait_for_selector(
                '.search-form-view__input', 
                state='visible',
                timeout=15000
            )
            logger.info("  [Поиск] Обертка поля ввода найдена.")
            
            # Кликаем по обертке чтобы активировать поле
            await search_wrapper.click()
            await asyncio.sleep(0.5)
            
            # Находим сам input внутри обертки
            search_box = await search_wrapper.query_selector('input')
            if not search_box:
                # Пробуем альтернативный селектор
                search_box = await page.wait_for_selector(
                    'input[data-testid="search-input"]', 
                    state='visible',
                    timeout=5000
                )
            
            if not search_box:
                raise Exception("Не удалось найти input внутри формы поиска")
                
            logger.info("  [Поиск] Input найден.")
            
            # Очищаем поле
            await search_box.fill("")
            await asyncio.sleep(0.5)
            
            # Вводим город и запрос
            search_text = f"{city} {query}"
            logger.info(f"  [Поиск] Ввод запроса: '{search_text}'")
            
            # Используем метод human_type_element из класса HumanBehavior (принимает объект элемента)
            await self.human.human_type_element(search_box, search_text)
            
            # Нажимаем Enter
            await search_box.press("Enter")
            logger.info("  [Поиск] Запрос отправлен (Enter).")
            
            # Ждем появления результатов
            await asyncio.sleep(5) 
            
        except Exception as e:
            logger.error(f"  [Ошибка] Не удалось найти поле поиска или ввести текст: {e}")
            await page.screenshot(path=f"error_yandex_search_{city}_{query}.png")
            raise Exception("Не удалось взаимодействовать с поиском Яндекса")

    async def parse_cards(self, page: Page, max_items: int) -> List[Dict]:
        """Собирает данные из списка организаций с использованием ваших селекторов"""
        items = []
        logger.info("  [Парсинг] Начинаем сбор данных из списка...")

        # Ждем появления списка результатов
        await asyncio.sleep(3)
        
        # Основной селектор карточки - используем тот который вы указали
        # search-business-snippet-view - это базовый класс карточки
        card_selector = '.search-business-snippet-view'
        
        logger.info(f"  [Парсинг] Поиск карточек по селектору: {card_selector}")
        
        # Ждем появления хотя бы одной карточки
        try:
            await page.wait_for_selector(card_selector, timeout=15000, state='visible')
        except Exception:
            logger.warning("  [Парсинг] Карточки не найдены за 15 секунд. Пробуем продолжить...")
            await page.screenshot(path="debug_yandex_nocards.png", full_page=True)
            return []
        
        cards = await page.query_selector_all(card_selector)
        logger.info(f"  [Парсинг] Найдено карточек: {len(cards)}")
        
        if not cards:
            return []

        # Функция для скролла контейнера со списком
        async def scroll_list():
            # Пытаемся найти контейнер со скроллом
            scroll_container = await page.query_selector('.scroll__container')
            if scroll_container:
                await scroll_container.evaluate('el => el.scrollTop += 800')
            else:
                # Скроллим страницу
                await page.evaluate('window.scrollBy(0, 800)')
            await asyncio.sleep(2)  # Ждем подгрузки
        
        # Скроллим и собираем карточки пока не наберем нужное количество
        no_progress_count = 0
        prev_count = len(cards)
        
        while len(cards) < max_items and no_progress_count < 3:
            await scroll_list()
            
            new_cards = await page.query_selector_all(card_selector)
            current_count = len(new_cards)
            
            logger.debug(f"  [Парсинг] Карточек в DOM: {current_count}")
            
            if current_count > prev_count:
                cards = new_cards
                prev_count = current_count
                no_progress_count = 0
                logger.info(f"  [Парсинг] Загружено новых карточек. Всего: {current_count}")
            else:
                no_progress_count += 1
                
        logger.info(f"  [Парсинг] Прокрутка завершена. Итого карточек: {len(cards)}")

        # Парсим каждую карточку
        for i, card in enumerate(cards[:max_items]):
            try:
                # Проверяем видимость
                if not await card.is_visible():
                    continue
                    
                # Название - search-business-snippet-view__title
                title_el = await card.query_selector('.search-business-snippet-view__title')
                name = (await title_el.inner_text()).strip() if title_el else "Без названия"
                
                # Категория - search-business-snippet-view__categories
                cat_el = await card.query_selector('.search-business-snippet-view__categories')
                category = (await cat_el.inner_text()).strip() if cat_el else ""
                
                # Адрес - search-business-snippet-view__sequence
                addr_el = await card.query_selector('.search-business-snippet-view__sequence')
                address = (await addr_el.inner_text()).strip() if addr_el else ""
                
                # Рейтинг - business-rating-badge-view__rating
                rating_el = await card.query_selector('.business-rating-badge-view__rating')
                rating = (await rating_el.inner_text()).strip() if rating_el else "N/A"
                
                # Количество оценок - business-rating-with-text-view__count
                count_el = await card.query_selector('.business-rating-with-text-view__count')
                reviews = (await count_el.inner_text()).strip() if count_el else "0"
                
                # Ссылка
                link_el = await card.query_selector('a.link')
                link = ""
                if link_el:
                    href = await link_el.get_attribute('href')
                    if href:
                        link = f"https://yandex.ru{href}" if href.startswith('/') else href
                
                item = {
                    'source': 'Yandex Maps',
                    'name': name,
                    'category': category,
                    'address': address,
                    'rating': rating,
                    'reviews': reviews,
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
                    
            except Exception as e:
                logger.error(f"  [Ошибка] При парсинге карточки #{i}: {e}")
                continue

        logger.info(f"  [Итого] Собрано уникальных объектов: {len(items)}")
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
