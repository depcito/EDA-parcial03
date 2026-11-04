"""Entidades del dominio: inmutables, con tipado estricto y validación en construcción."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum

from .errors import ValidationError


class Category(str, Enum):
    MEDICO = "MEDICO"
    VIVERES = "VIVERES"
    AGUA = "AGUA"
    REFUGIO = "REFUGIO"
    RESCATE = "RESCATE"
    FONDOS = "FONDOS"


CATEGORY_UNITS = {
    Category.MEDICO: "kit",
    Category.VIVERES: "racion",
    Category.AGUA: "litro",
    Category.REFUGIO: "kit",
    Category.RESCATE: "herramienta",
    Category.FONDOS: "COP",
}


class LotStatus(str, Enum):
    AVAILABLE = "DISPONIBLE"
    ASSIGNED = "ASIGNADO"
    EXPIRED = "VENCIDO"


class DonorKind(str, Enum):
    PERSONA = "PERSONA"
    ONG = "ONG"
    EMPRESA = "EMPRESA"
    INTERNACIONAL = "INTERNACIONAL"
    GOBIERNO = "GOBIERNO"


class HubKind(str, Enum):
    AEROPUERTO = "AEROPUERTO"
    PUERTO = "PUERTO"
    ACOPIO = "ACOPIO"


class RoadStatus(str, Enum):
    OPEN = "ABIERTA"
    RESTRICTED = "RESTRINGIDA"
    CLOSED = "CERRADA"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _nonempty(value: str, name: str) -> None:
    _require(isinstance(value, str) and value.strip() != "", f"'{name}' no puede estar vacío")


def _count(value: int, name: str, minimum: int = 0) -> None:
    _require(isinstance(value, int) and not isinstance(value, bool), f"'{name}' debe ser entero")
    _require(value >= minimum, f"'{name}' debe ser >= {minimum} (recibido {value})")


def _real(value: float, name: str, minimum: float = 0.0) -> None:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"'{name}' debe ser numérico")
    _require(math.isfinite(value), f"'{name}' debe ser finito")
    _require(value >= minimum, f"'{name}' debe ser >= {minimum} (recibido {value})")


def _coords(lat: float, lon: float) -> None:
    _real(lat, "lat", -5.0)
    _real(lon, "lon", -82.0)
    _require(lat <= 14.0 and lon <= -66.0, "coordenadas fuera del territorio colombiano")


@dataclass(frozen=True)
class EventInfo:
    name: str
    event_date: date
    epicenter_lat: float
    epicenter_lon: float
    magnitude: float


@dataclass(frozen=True)
class Donor:
    donor_id: str
    name: str
    kind: DonorKind
    origin: str

    def __post_init__(self) -> None:
        _nonempty(self.donor_id, "donor_id")
        _nonempty(self.name, "name")
        _nonempty(self.origin, "origin")


@dataclass(frozen=True)
class Hub:
    """Centro de acopio / punto de entrada (aeropuerto, puerto o acopio regional)."""

    hub_id: str
    name: str
    department: str
    kind: HubKind
    lat: float
    lon: float
    capacity_m3: float

    def __post_init__(self) -> None:
        _nonempty(self.hub_id, "hub_id")
        _nonempty(self.name, "name")
        _coords(self.lat, self.lon)
        _real(self.capacity_m3, "capacity_m3")
        _require(self.capacity_m3 > 0, "'capacity_m3' debe ser > 0")


@dataclass(frozen=True)
class Lot:
    """Lote de ayuda. `available` baja con cada asignación; el lote nunca se muta."""

    lot_id: str
    donor_id: str
    category: Category
    description: str
    quantity: int
    unit: str
    weight_kg: float
    volume_m3: float
    hub_id: str
    received: date
    expiry: date | None = None
    cold_chain: bool = False
    available: int = -1
    status: LotStatus = LotStatus.AVAILABLE

    def __post_init__(self) -> None:
        _nonempty(self.lot_id, "lot_id")
        _nonempty(self.donor_id, "donor_id")
        _nonempty(self.hub_id, "hub_id")
        _nonempty(self.description, "description")
        _nonempty(self.unit, "unit")
        _count(self.quantity, "quantity")
        if self.available == -1:
            object.__setattr__(self, "available", self.quantity)
        _count(self.available, "available")
        _require(self.available <= self.quantity, "'available' no puede superar 'quantity'")
        _real(self.weight_kg, "weight_kg")
        _real(self.volume_m3, "volume_m3")
        if self.expiry is not None:
            _require(self.expiry > self.received, "la caducidad debe ser posterior a la recepción")
        _require(
            self.status != LotStatus.ASSIGNED or self.available == 0,
            "un lote ASIGNADO no puede tener unidades disponibles",
        )

    @property
    def is_funds(self) -> bool:
        return self.category is Category.FONDOS

    @property
    def shelf_key(self) -> date:
        return self.expiry if self.expiry is not None else date.max

    def take(self, n: int) -> "Lot":
        """Devuelve el lote tras descontar `n` unidades (ASIGNADO si queda en cero)."""
        _require(0 < n <= self.available, f"no se pueden tomar {n} de {self.available} disponibles")
        left = self.available - n
        status = LotStatus.ASSIGNED if left == 0 else self.status
        return replace(self, available=left, status=status)


@dataclass(frozen=True)
class Municipality:
    muni_id: str
    name: str
    department: str
    zone: str
    population: int
    lat: float
    lon: float
    urgency: int
    injured: int
    dead: int
    missing: int
    displaced: int
    damaged_homes: int
    needs: tuple[tuple[Category, int], ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.muni_id, "muni_id")
        _nonempty(self.name, "name")
        _nonempty(self.zone, "zone")
        _count(self.population, "population", 1)
        _coords(self.lat, self.lon)
        _require(isinstance(self.urgency, int) and 1 <= self.urgency <= 5, "'urgency' debe estar entre 1 y 5")
        for f in ("injured", "dead", "missing", "displaced", "damaged_homes"):
            _count(getattr(self, f), f)
        _require(
            self.injured + self.dead + self.missing <= self.population,
            "víctimas superan la población del municipio",
        )
        _require(self.displaced <= self.population, "desplazados superan la población")
        for cat, qty in self.needs:
            _require(isinstance(cat, Category), "necesidad con categoría inválida")
            _count(qty, f"need_{cat.value}")

    def need(self, cat: Category) -> int:
        return sum(q for c, q in self.needs if c is cat)

    @property
    def severity_index(self) -> float:
        """Víctimas ponderadas por cada 1.000 habitantes (5·muertos + 3·desaparecidos + 2·heridos + desplazados)."""
        weighted = 5 * self.dead + 3 * self.missing + 2 * self.injured + self.displaced
        return 1000.0 * weighted / self.population


@dataclass(frozen=True)
class Road:
    a: str
    b: str
    km: float
    speed_kmh: float
    status: RoadStatus

    def __post_init__(self) -> None:
        _nonempty(self.a, "a")
        _nonempty(self.b, "b")
        _require(self.a != self.b, "una carretera no puede unir un nodo consigo mismo")
        _real(self.km, "km")
        _require(self.km > 0, "'km' debe ser > 0")
        _real(self.speed_kmh, "speed_kmh")
        _require(0 < self.speed_kmh <= 130, "'speed_kmh' debe estar en (0, 130]")

    @property
    def hours(self) -> float:
        """Tiempo estimado; las vías restringidas operan a la mitad de velocidad."""
        if self.status is RoadStatus.CLOSED:
            return math.inf
        factor = 0.5 if self.status is RoadStatus.RESTRICTED else 1.0
        return self.km / (self.speed_kmh * factor)


def check_lot_temporal(lot: Lot, event_date: date) -> None:
    """Coherencia temporal: recepción desde el evento y caducidad posterior a él."""
    _require(lot.received >= event_date, f"lote {lot.lot_id}: recibido antes del evento")
    if lot.expiry is not None:
        _require(lot.expiry > event_date, f"lote {lot.lot_id}: caducidad no posterior al evento")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))
