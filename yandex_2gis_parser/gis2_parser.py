"""
Парсер 2ГИС (2GIS)
"""
import asyncio
import re
from typing import List, Dict, Optional
from playwright.async_api import Page, BrowserContext

try:
    from .human_behavior import HumanBehaviorSimulator
except ImportError:
    from human_behavior import HumanBehaviorSimulator


class Gis2Parser:
    """Парсер для 2ГИС"""
    
    def __init__(self, context: BrowserContext, config: dict):
        self.context = context
        self.config = config
        self.human = HumanBehaviorSimulator(config)
        self.base_url = "https://2gis.ru"
        
    async def search(self, page: Page, query: str, city: str):
        """Выполнение поиска по запросу и городу"""
        # Формируем URL для города
        city_slug = self._get_city_slug(city)
        url = f"{self.base_url}/{city_slug}"
        
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await self.human.random_delay(2, 4)
        
        # Ищем поле ввода поиска
        search_selectors = [
            "input[placeholder*='Поиск']",
            "input[data-name='SearchInput']",
            ".header-search-input",
            "input.search-input"
        ]
        
        search_box = None
        for selector in search_selectors:
            try:
                search_box = await page.wait_for_selector(selector, timeout=5000)
                if search_box:
                    break
            except:
                continue
        
        if not search_box:
            # Пробуем найти через другие селекторы
            search_box = await page.query_selector("input[type='text']")
            
        if search_box:
            # Вводим запрос
            full_query = f"{query}"
            await self.human.human_type(page, search_selectors[0], full_query)
            
            # Нажимаем Enter
            await page.keyboard.press("Enter")
            await self.human.random_delay(3, 6)
            
            # Ждем загрузки результатов
            try:
                await page.wait_for_selector(".rubricCatalogList, .search-results", timeout=15000)
            except:
                pass
        else:
            print("Не найдено поле поиска на 2ГИС")
            
    def _get_city_slug(self, city: str) -> str:
        """Преобразование названия города в slug для URL"""
        city_mapping = {
            'москва': 'moskva',
            'санкт-петербург': 'sankt-peterburg',
            'новосибирск': 'novosibirsk',
            'екатеринбург': 'ekaterinburg',
            'казань': 'kazan',
            'нижний новгород': 'nizhnij_novgorod',
            'челябинск': 'chelyabinsk',
            'самара': 'samara',
            'омск': 'omsk',
            'ростов-на-дону': 'rostov-na-donu',
            'уфа': 'ufa',
            'красноярск': 'krasnoyarsk',
            'воронеж': 'voronezh',
            'пермь': 'perm',
            'волгоград': 'volgograd'
        }
        
        city_lower = city.lower()
        return city_mapping.get(city_lower, city_lower.replace(' ', '_'))
        
    async def scroll_and_collect(self, page: Page, max_items: int = 50) -> List[Dict]:
        """Прокрутка списка и сбор данных об объектах"""
        items = []
        seen_ids = set()
        
        # Находим контейнер со списком результатов
        list_selectors = [
            ".rubricCatalogList",
            ".search-results",
            "[data-name='SearchResults']",
            ".catalog-list"
        ]
        
        list_container = None
        for selector in list_selectors:
            list_container = await page.query_selector(selector)
            if list_container:
                break
        
        if not list_container:
            # Если не нашли конкретный контейнер, пробуем искать карточки напрямую
            return await self._collect_items_direct(page, max_items, seen_ids)
            
        max_scrolls = 20
        scrolls_done = 0
        
        while scrolls_done < max_scrolls and len(items) < max_items:
            # Прокручиваем с человеческим поведением
            await self.human.human_scroll(page, list_container)
            
            # Собираем элементы
            item_cards = await page.query_selector_all(
                ".rubricCatalogItem, .search-result-item, [data-name='SearchResultItem']"
            )
            
            for card in item_cards:
                try:
                    item_id = await card.get_attribute('data-id') or await card.get_attribute('id')
                    if item_id and item_id in seen_ids:
                        continue
                    if item_id:
                        seen_ids.add(item_id)
                        
                    data = await self.extract_item_data(page, card)
                    if data:
                        items.append(data)
                        
                    if len(items) >= max_items:
                        break
                except Exception as e:
                    continue
                    
            scrolls_done += 1
            
            # Проверяем, достигли ли конца списка
            try:
                scroll_height = await list_container.evaluate('el => el.scrollHeight')
                client_height = await list_container.evaluate('el => el.clientHeight')
                scroll_top = await list_container.evaluate('el => el.scrollTop')
                
                if scroll_top + client_height >= scroll_height - 10:
                    break
            except:
                pass
                
        return items[:max_items]
        
    async def _collect_items_direct(self, page: Page, max_items: int, seen_ids: set) -> List[Dict]:
        """Сбор элементов без конкретного контейнера"""
        items = []
        
        # Прокручиваем всю страницу
        await self.human.human_scroll(page)
        
        item_cards = await page.query_selector_all(
            ".rubricCatalogItem, .search-result-item, [data-name='SearchResultItem'], .catalog-item"
        )
        
        for card in item_cards:
            if len(items) >= max_items:
                break
                
            try:
                item_id = await card.get_attribute('data-id') or await card.get_attribute('id')
                if item_id and item_id in seen_ids:
                    continue
                if item_id:
                    seen_ids.add(item_id)
                    
                data = await self.extract_item_data(page, card)
                if data:
                    items.append(data)
            except:
                continue
                
        return items
        
    async def extract_item_data(self, page: Page, card) -> Optional[Dict]:
        """Извлечение данных из карточки объекта"""
        try:
            data = {
                'source': 'gis_2',
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
            
            # Название
            name_el = await card.query_selector(
                ".rubricCatalogItem__nameLink, .search-result-item__name, [data-name='ItemName']"
            )
            if name_el:
                data['name'] = (await name_el.inner_text()).strip()
                
            # Рейтинг
            rating_el = await card.query_selector(
                ".rating-value, .search-result-item__rating, [data-name='RatingValue']"
            )
            if rating_el:
                rating_text = await rating_el.inner_text()
                rating_match = re.search(r'([\d,]+)', rating_text.replace(',', '.'))
                if rating_match:
                    data['rating'] = float(rating_match.group(1).replace(',', '.'))
                    
            # Количество отзывов
            reviews_el = await card.query_selector(
                ".reviews-count, .search-result-item__reviews"
            )
            if reviews_el:
                reviews_text = await reviews_el.inner_text()
                reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', ''))
                if reviews_match:
                    data['reviews_count'] = int(reviews_match.group(1))
                    
            # Адрес
            address_el = await card.query_selector(
                ".rubricCatalogItem__address, .search-result-item__address, [data-name='Address']"
            )
            if address_el:
                data['address'] = (await address_el.inner_text()).strip()
                
            # Категория
            category_el = await card.query_selector(
                ".rubricCatalogItem__rubric, .search-result-item__category"
            )
            if category_el:
                data['category'] = (await category_el.inner_text()).strip()
                
            # Телефон
            phone_el = await card.query_selector(
                ".phone, .search-result-item__phone, [data-name='Phone']"
            )
            if phone_el:
                data['phone'] = (await phone_el.inner_text()).strip()
                
            # Часы работы
            hours_el = await card.query_selector(
                ".work-time, .search-result-item__hours, [data-name='WorkTime']"
            )
            if hours_el:
                data['hours'] = (await hours_el.inner_text()).strip()
                
            # Ссылка
            link_el = await card.query_selector("a[href*='/']")
            if link_el:
                href = await link_el.get_attribute('href')
                if href:
                    data['url'] = href if href.startswith('http') else f"https://2gis.ru{href}"
                    
            return data
            
        except Exception as e:
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
