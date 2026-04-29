# Инициализация пакета
try:
    from .main import MapsParser
except ImportError:
    from main import MapsParser

__all__ = ['MapsParser']
