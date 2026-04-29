"""
Модуль для имитации человеческого поведения браузера
"""
import random
import asyncio
from playwright.async_api import Page


class HumanBehaviorSimulator:
    """Класс для симуляции человеческого поведения при парсинге"""
    
    def __init__(self, config: dict = None):
        # Если конфиг не передан, используем значения по умолчанию
        if config is None:
            config = {
                'parsing_settings': {
                    'mouse_movement_enabled': True,
                    'random_scroll_enabled': True,
                    'delay_between_actions_min': 2,
                    'delay_between_actions_max': 5,
                    'scroll_pause_min': 1,
                    'scroll_pause_max': 3
                }
            }
        self.config = config
        self.mouse_enabled = config.get('parsing_settings', {}).get('mouse_movement_enabled', True)
        self.scroll_enabled = config.get('parsing_settings', {}).get('random_scroll_enabled', True)
        
    async def random_delay(self, min_sec: float = None, max_sec: float = None):
        """Случайная задержка между действиями"""
        if min_sec is None:
            min_sec = self.config['parsing_settings'].get('delay_between_actions_min', 2)
        if max_sec is None:
            max_sec = self.config['parsing_settings'].get('delay_between_actions_max', 5)
        
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
        
    async def human_mouse_move(self, page: Page, start_x: int, start_y: int, end_x: int, end_y: int):
        """Имитация человеческого движения мыши по кривой Безье"""
        if not self.mouse_enabled:
            await page.mouse.move(end_x, end_y)
            return
            
        # Разбиваем путь на сегменты с случайными отклонениями
        steps = random.randint(10, 30)
        duration = random.uniform(300, 800)  # миллисекунды
        
        for i in range(steps + 1):
            t = i / steps
            # Квадратичная кривая Безье с контрольной точкой
            control_x = (start_x + end_x) / 2 + random.randint(-50, 50)
            control_y = (start_y + end_y) / 2 + random.randint(-50, 50)
            
            x = int((1 - t) ** 2 * start_x + 2 * (1 - t) * t * control_x + t ** 2 * end_x)
            y = int((1 - t) ** 2 * start_y + 2 * (1 - t) * t * control_y + t ** 2 * end_y)
            
            await page.mouse.move(x, y)
            await asyncio.sleep(duration / steps / 1000)
            
    async def human_scroll(self, page: Page, element=None):
        """Имитация человеческой прокрутки страницы"""
        if not self.scroll_enabled:
            return
            
        # Получаем размеры области прокрутки
        if element:
            scroll_height = await element.evaluate('el => el.scrollHeight')
            client_height = await element.evaluate('el => el.clientHeight')
        else:
            scroll_height = await page.evaluate('() => document.documentElement.scrollHeight')
            client_height = await page.evaluate('() => document.documentElement.clientHeight')
            
        max_scroll = scroll_height - client_height
        if max_scroll <= 0:
            return
            
        current_scroll = 0
        while current_scroll < max_scroll:
            # Случайный размер шага прокрутки
            scroll_step = random.randint(100, 400)
            current_scroll = min(current_scroll + scroll_step, max_scroll)
            
            if element:
                await element.evaluate(f'el => el.scrollTo({{top: {current_scroll}, behavior: "smooth"}})')
            else:
                await page.evaluate(f'window.scrollTo({{top: {current_scroll}, behavior: "smooth"}})')
                
            # Пауза между скроллами
            pause = random.uniform(
                self.config['parsing_settings'].get('scroll_pause_min', 1),
                self.config['parsing_settings'].get('scroll_pause_max', 3)
            )
            await asyncio.sleep(pause)
            
            # Иногда делаем небольшую прокрутку назад (как люди)
            if random.random() < 0.2 and current_scroll > 50:
                back_step = random.randint(20, 100)
                current_scroll = max(0, current_scroll - back_step)
                if element:
                    await element.evaluate(f'el => el.scrollTo({{top: {current_scroll}, behavior: "smooth"}})')
                else:
                    await page.evaluate(f'window.scrollTo({{top: {current_scroll}, behavior: "smooth"}})')
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
    async def human_click(self, page: Page, selector: str):
        """Человеческий клик по элементу"""
        element = await page.wait_for_selector(selector)
        box = await element.bounding_box()
        
        if box:
            # Кликаем в случайную точку внутри элемента (не строго по центру)
            x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
            y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
            
            # Двигаем мышь к элементу
            await self.human_mouse_move(
                page,
                await page.evaluate('() => window.mouseX || 0'),
                await page.evaluate('() => window.mouseY || 0'),
                int(x), int(y)
            )
            
            # Небольшая пауза перед кликом
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Клик
            await page.mouse.click(x, y)
            await self.random_delay(0.5, 1.5)
        else:
            await element.click()
            await self.random_delay(0.5, 1.5)
            
    async def human_scroll_page(self, page: Page):
        """Имитация человеческой прокрутки всей страницы"""
        if not self.scroll_enabled:
            return
            
        scroll_height = await page.evaluate('() => document.documentElement.scrollHeight')
        client_height = await page.evaluate('() => document.documentElement.clientHeight')
        
        max_scroll = scroll_height - client_height
        if max_scroll <= 0:
            return
            
        current_scroll = await page.evaluate('() => window.scrollY')
        
        # Случайный размер шага прокрутки
        scroll_step = random.randint(200, 500)
        new_scroll = min(current_scroll + scroll_step, max_scroll)
        
        await page.evaluate(f'window.scrollTo({{top: {new_scroll}, behavior: "smooth"}})')
        
        # Пауза между скроллами
        pause = random.uniform(1.5, 3.5)
        await asyncio.sleep(pause)
        
        # Иногда делаем небольшую прокрутку назад (как люди)
        if random.random() < 0.2 and new_scroll > 50:
            back_step = random.randint(30, 100)
            new_scroll = max(0, new_scroll - back_step)
            await page.evaluate(f'window.scrollTo({{top: {new_scroll}, behavior: "smooth"}})')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
    async def human_type(self, page: Page, selector: str, text: str):
        """Человеческий ввод текста с случайными задержками (принимает селектор)"""
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        
        # Очищаем поле
        await page.locator(selector).clear()
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        # Вводим текст посимвольно с случайными задержками
        for char in text:
            await page.keyboard.type(char)
            # Случайная задержка между символами (люди печатают неравномерно)
            if random.random() < 0.1:  # 10% шанс на большую паузу
                await asyncio.sleep(random.uniform(0.3, 0.8))
            else:
                await asyncio.sleep(random.uniform(0.05, 0.15))
                
        await self.random_delay(0.5, 1.0)

    async def human_type_element(self, element, text: str):
        """Человеческий ввод текста в элемент (принимает объект элемента)"""
        await element.click()
        await asyncio.sleep(random.uniform(0.3, 0.7))
        
        # Очищаем поле через элемент
        await element.fill("")
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        # Вводим текст посимвольно с случайными задержками
        for char in text:
            await element.press(f"Key:{char}" if len(char) == 1 and char.isalpha() else char)
            # Случайная задержка между символами (люди печатают неравномерно)
            if random.random() < 0.1:  # 10% шанс на большую паузу
                await asyncio.sleep(random.uniform(0.3, 0.8))
            else:
                await asyncio.sleep(random.uniform(0.05, 0.15))
                
        await self.random_delay(0.5, 1.0)


# Алиас для обратной совместимости
HumanBehavior = HumanBehaviorSimulator


# Методы-обертки для удобства вызова (как в старых версиях)
async def type_text(page, selector: str, text: str):
    """Обертка для human_type"""
    simulator = HumanBehaviorSimulator()
    await simulator.human_type(page, selector, text)


async def scroll_element(page, element, direction: str = 'down', amount: int = 400):
    """Обертка для скролла элемента"""
    # Простая реализация скролла элемента
    if direction == 'down':
        await element.evaluate(f'el => el.scrollTop += {amount}')
    elif direction == 'up':
        await element.evaluate(f'el => el.scrollTop -= {amount}')
    await asyncio.sleep(0.5)


async def scroll_page(page, direction: str = 'down', pixels: int = 400):
    """Обертка для скролла страницы"""
    if direction == 'down':
        await page.evaluate(f'window.scrollBy(0, {pixels})')
    elif direction == 'up':
        await page.evaluate(f'window.scrollBy(0, -{pixels})')
    await asyncio.sleep(0.5)
