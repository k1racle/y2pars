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
        await page.goto(self.base_url, wait_until='networkidle')
        await self.human.random_delay(2, 4)
        
        # Ищем поле ввода поиска
        search_selector = "input[aria-label='Поиск']", "input.search-input", "#search-input"
        search_box = None
        
        for selector in search_selector:
            try:
                search_box = await page.wait_for_selector(selector, timeout=5000)
                if search_box:
                    break
            except:
                continue
                
        if not search_box:
            # Альтернативный поиск через клики
            await page.click("button:has-text('Москва'), button:has-text('Санкт-Петербург')", timeout=10000)
            await self.human.random_delay(1, 2)
            
        # Вводим город и запрос
        full_query = f"{city} {query}"
        await self.human.human_type(page, search_selector[0], full_query)
        
        # Нажимаем Enter или кнопку поиска
        await page.keyboard.press("Enter")
        await self.human.random_delay(3, 5)
        
        # Ждем загрузки результатов
        try:
            await page.wait_for_selector(".business-list-view__list", timeout=15000)
        except:
            pass
            
    async def scroll_and_collect(self, page: Page, max_items: int = 50) -> List[Dict]:
        """Прокрутка списка и сбор данных об объектах"""
        items = []
        seen_ids = set()
        
        # Находим контейнер со списком
        list_container = await page.query_selector(".business-list-view__list")
        
        if not list_container:
            return items
            
        max_scrolls = 20
        scrolls_done = 0
        
        while scrolls_done < max_scrolls and len(items) < max_items:
            # Прокручиваем с человеческим поведением
            await self.human.human_scroll(page, list_container)
            
            # Собираем элементы
            item_cards = await page.query_selector_all(".business-card-view__content")
            
            for card in item_cards:
                try:
                    item_id = await card.get_attribute('data-business-id') or await card.get_attribute('id')
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
            scroll_height = await list_container.evaluate('el => el.scrollHeight')
            client_height = await list_container.evaluate('el => el.clientHeight')
            scroll_top = await list_container.evaluate('el => el.scrollTop')
            
            if scroll_top + client_height >= scroll_height - 10:
                break
                
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
            
            # Название
            name_el = await card.query_selector(".business-card-view__header-title")
            if name_el:
                data['name'] = (await name_el.inner_text()).strip()
                
            # Рейтинг
            rating_el = await card.query_selector(".business-card-view__rating")
            if rating_el:
                rating_text = await rating_el.inner_text()
                rating_match = re.search(r'([\d,]+)', rating_text.replace(',', '.'))
                if rating_match:
                    data['rating'] = float(rating_match.group(1).replace(',', '.'))
                    
            # Количество отзывов
            reviews_el = await card.query_selector(".business-card-view__reviews-count")
            if reviews_el:
                reviews_text = await reviews_el.inner_text()
                reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', ''))
                if reviews_match:
                    data['reviews_count'] = int(reviews_match.group(1))
                    
            # Адрес
            address_el = await card.query_selector(".business-card-view__address")
            if address_el:
                data['address'] = (await address_el.inner_text()).strip()
                
            # Категория
            category_el = await card.query_selector(".business-card-view__subtitle")
            if category_el:
                data['category'] = (await category_el.inner_text()).strip()
                
            # Ссылка на объект
            link_el = await card.query_selector("a.business-card-view__link")
            if link_el:
                href = await link_el.get_attribute('href')
                if href:
                    data['url'] = href if href.startswith('http') else f"https://yandex.ru{href}"
                    
            # Для подробной информации нужно кликнуть на карточку
            # Это можно сделать отдельно при необходимости
            
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
