"""
Парсер Яндекс Карт
"""
import asyncio
import re
from typing import List, Dict, Optional
from playwright.async_api import Page, BrowserContext

try:
    from .human_behavior import HumanBehaviorSimulator
except ImportError:
    from human_behavior import HumanBehaviorSimulator


class YandexMapsParser:
    """Парсер для Яндекс Карт"""
    
    def __init__(self, context: BrowserContext, config: dict):
        self.context = context
        self.config = config
        self.human = HumanBehaviorSimulator(config)
        self.base_url = "https://yandex.ru/maps"
        
    async def search(self, page: Page, query: str, city: str):
        """Выполнение поиска по запросу и городу"""
        # Переходим сразу на карту с городом
        self.base_url = f"https://yandex.ru/maps/{self.get_city_slug(city)}"
        await page.goto(self.base_url, wait_until='domcontentloaded', timeout=60000)
        await self.human.random_delay(3, 5)
        
        # Ищем поле ввода поиска - используем разные подходы
        search_box = None
        selectors = [
            "input[role='searchbox']",
            "input[aria-label*='Поиск']",
            "input[placeholder*='Поиск']",
            ".search-input input",
            "input[data-testid='search-input']",
            "header input",
            "input[type='text']"
        ]
        
        for selector in selectors:
            try:
                search_box = await page.wait_for_selector(selector, timeout=3000)
                if search_box:
                    print(f"Найдено поле поиска по селектору: {selector}")
                    break
            except:
                continue
        
        if not search_box:
            # Пробуем кликнуть по области поиска
            try:
                await page.click("header", timeout=5000)
                await self.human.random_delay(1, 2)
                search_box = await page.wait_for_selector("input", timeout=5000)
            except:
                pass
        
        if not search_box:
            raise Exception("Не удалось найти поле поиска на странице Яндекс Карт")
            
        # Фокусируемся на поле и очищаем его
        await search_box.focus()
        await self.human.random_delay(0.5, 1)
        
        # Выделяем всё и удаляем (Ctrl+A, Delete)
        await page.keyboard.press("Control+a")
        await self.human.random_delay(0.3, 0.7)
        await page.keyboard.press("Delete")
        await self.human.random_delay(0.5, 1)
        
        # Вводим полный запрос: город + тип объекта
        full_query = f"{query}"
        print(f"Вводим запрос: '{full_query}' для города {city}")
        
        # Вводим посимвольно с задержками
        for char in full_query:
            await page.keyboard.type(char)
            await self.human.random_delay(0.05, 0.2)
        
        await self.human.random_delay(1, 2)
        
        # Нажимаем Enter
        await page.keyboard.press("Enter")
        await self.human.random_delay(4, 7)
        
        # Ждем загрузки результатов - ищем разные индикаторы
        result_selectors = [
            ".business-list-view__list",
            "[data-business-list]",
            ".search-results",
            ".organizations-list",
            "article[data-business-id]"
        ]
        
        for selector in result_selectors:
            try:
                await page.wait_for_selector(selector, timeout=10000)
                print(f"Результаты найдены по селектору: {selector}")
                break
            except:
                continue
        
        # Дополнительная пауза для полной загрузки
        await self.human.random_delay(2, 4)
    
    def get_city_slug(self, city: str) -> str:
        """Получение slug города для URL Яндекс Карт"""
        city_slugs = {
            'москва': 'moscow',
            'санкт-петербург': 'saint-petersburg',
            'спб': 'saint-petersburg',
            'новосибирск': 'novosibirsk',
            'екатеринбург': 'yekaterinburg',
            'казань': 'kazan',
            'нижний новгород': 'nizhny-novgorod',
            'челябинск': 'chelyabinsk',
            'самара': 'samara',
            'омск': 'omsk',
            'ростов-на-дону': 'rostov-na-donu',
            'уфа': 'ufa',
            'красноярск': 'krasnoyarsk',
            'воронеж': 'voronezh',
            'пермь': 'perm',
            'волгоград': 'volgograd',
            'краснодар': 'krasnodar',
        }
        return city_slugs.get(city.lower(), city.lower().replace(' ', '-'))
            
    async def scroll_and_collect(self, page: Page, max_items: int = 50) -> List[Dict]:
        """Прокрутка списка и сбор данных об объектах"""
        items = []
        seen_ids = set()
        
        # Ждем немного больше для полной загрузки
        await self.human.random_delay(2, 4)
        
        # Находим контейнер со списком - используем разные селекторы
        list_container = None
        container_selectors = [
            ".business-list-view__list",
            "[data-business-list]",
            ".search-results",
            ".organizations-list",
            "div[role='list']"
        ]
        
        for selector in container_selectors:
            try:
                list_container = await page.query_selector(selector)
                if list_container:
                    print(f"Контейнер списка найден: {selector}")
                    break
            except:
                continue
        
        if not list_container:
            # Если не нашли список, пробуем найти карточки напрямую
            print("Список не найден, пробуем найти карточки напрямую")
            await self.human.random_delay(1, 2)
        
        max_scrolls = 20
        scrolls_done = 0
        
        while scrolls_done < max_scrolls and len(items) < max_items:
            # Прокручиваем страницу или контейнер
            if list_container:
                await self.human.human_scroll(page, list_container)
            else:
                # Прокручиваем всю страницу
                await self.human.human_scroll_page(page)
            
            # Собираем элементы - используем разные селекторы для карточек
            card_selectors = [
                ".business-card-view__content",
                "article[data-business-id]",
                "[data-business-card]",
                ".search-snippet-view",
                "div[role='listitem']",
                ".business-list-item"
            ]
            
            item_cards = []
            for selector in card_selectors:
                try:
                    item_cards = await page.query_selector_all(selector)
                    if item_cards:
                        print(f"Найдено карточек по селектору {selector}: {len(item_cards)}")
                        break
                except:
                    continue
            
            if not item_cards:
                print("Карточки не найдены, ждем...")
                await self.human.random_delay(2, 3)
                scrolls_done += 1
                continue
            
            for card in item_cards:
                try:
                    item_id = await card.get_attribute('data-business-id') or await card.get_attribute('id')
                    if item_id and item_id in seen_ids:
                        continue
                    if item_id:
                        seen_ids.add(item_id)
                        
                    data = await self.extract_item_data(page, card)
                    if data and data.get('name'):
                        items.append(data)
                        
                    if len(items) >= max_items:
                        break
                except Exception as e:
                    continue
                    
            scrolls_done += 1
            
            # Проверяем, достигли ли конца списка
            if list_container:
                try:
                    scroll_height = await list_container.evaluate('el => el.scrollHeight')
                    client_height = await list_container.evaluate('el => el.clientHeight')
                    scroll_top = await list_container.evaluate('el => el.scrollTop')
                    
                    if scroll_top + client_height >= scroll_height - 10:
                        print("Достигнут конец списка")
                        break
                except:
                    pass
            
            # Небольшая пауза между скроллами
            await self.human.random_delay(1, 2)
            
        print(f"Всего собрано объектов: {len(items)}")
        return items[:max_items]
        
    async def extract_item_data(self, page: Page, card) -> Optional[Dict]:
        """Извлечение данных из карточки объекта"""
        try:
            data = {
                'source': 'yandex_maps',
                'name': None,
                'address': None,
                'rating': None,
                'reviews_count': None,
                'phone': None,
                'website': None,
                'category': None,
                'hours': None,
                'url': None
            }
            
            # Название - ищем по разным селекторам
            name_selectors = [
                ".business-card-view__header-title",
                ".search-snippet-view__title",
                "[data-business-card-title]",
                "a[data-gu]",
                ".business-list-item__name"
            ]
            for selector in name_selectors:
                try:
                    name_el = await card.query_selector(selector)
                    if name_el:
                        data['name'] = (await name_el.inner_text()).strip()
                        break
                except:
                    continue
            
            # Если название не найдено, пробуем найти его в тексте карточки
            if not data['name']:
                try:
                    data['name'] = (await card.inner_text()).split('\n')[0].strip()[:100]
                except:
                    pass
            
            # Рейтинг - ищем по разным селекторам
            rating_selectors = [
                ".business-card-view__rating",
                ".rating-value",
                "[class*='rating']",
                ".search-snippet-view__rating"
            ]
            for selector in rating_selectors:
                try:
                    rating_el = await card.query_selector(selector)
                    if rating_el:
                        rating_text = await rating_el.inner_text()
                        rating_match = re.search(r'([\d,]+)', rating_text.replace(',', '.'))
                        if rating_match:
                            data['rating'] = float(rating_match.group(1).replace(',', '.'))
                            break
                except:
                    continue
                    
            # Количество отзывов
            reviews_selectors = [
                ".business-card-view__reviews-count",
                "[class*='review']",
                ".search-snippet-view__reviews"
            ]
            for selector in reviews_selectors:
                try:
                    reviews_el = await card.query_selector(selector)
                    if reviews_el:
                        reviews_text = await reviews_el.inner_text()
                        reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', ''))
                        if reviews_match:
                            data['reviews_count'] = int(reviews_match.group(1))
                            break
                except:
                    continue
                    
            # Адрес
            address_selectors = [
                ".business-card-view__address",
                ".search-snippet-view__address",
                "[class*='address']"
            ]
            for selector in address_selectors:
                try:
                    address_el = await card.query_selector(selector)
                    if address_el:
                        data['address'] = (await address_el.inner_text()).strip()
                        break
                except:
                    continue
                
            # Категория
            category_selectors = [
                ".business-card-view__subtitle",
                ".search-snippet-view__subtitle",
                "[class*='category']"
            ]
            for selector in category_selectors:
                try:
                    category_el = await card.query_selector(selector)
                    if category_el:
                        data['category'] = (await category_el.inner_text()).strip()
                        break
                except:
                    continue
                
            # Ссылка на объект
            link_selectors = [
                "a.business-card-view__link",
                "a.search-snippet-view__link",
                "a[data-gu]",
                "a[href*='/maps/']"
            ]
            for selector in link_selectors:
                try:
                    link_el = await card.query_selector(selector)
                    if link_el:
                        href = await link_el.get_attribute('href')
                        if href:
                            data['url'] = href if href.startswith('http') else f"https://yandex.ru{href}"
                            break
                except:
                    continue
                
            return data
            
        except Exception as e:
            print(f"Ошибка при извлечении данных: {e}")
            return None
            
    async def parse_city_query(self, city: str, query: str, max_items: int = 50) -> List[Dict]:
        """Полный цикл парсинга для города и запроса"""
        page = await self.context.new_page()
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Поиск
            await self.search(page, query, city)
            
            # Сбор данных
            items = await self.scroll_and_collect(page, max_items)
            
            # Добавляем информацию о поиске
            for item in items:
                item['city'] = city
                item['search_query'] = query
                
            return items
        finally:
            await page.close()
