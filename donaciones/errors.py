"""Excepciones del dominio."""


class ValidationError(ValueError):
    """Un dato no cumple tipo, rango o coherencia."""


class DataSourceError(Exception):
    """La fuente de datos no se pudo leer o está estructuralmente rota."""


class DonationError(Exception):
    """Una operación del sistema no es válida en el estado actual."""
