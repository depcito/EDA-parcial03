"""Lectura, validación y serialización (CSV / JSON) de las fuentes de datos.

Política de errores:
  - Fallas de I/O o de estructura global (archivo ausente, encabezado roto) -> DataSourceError.
  - Fallas por registro (campo nulo, tipo inválido, rango, referencia huérfana) -> se
    acumulan como RowError y el registro se omite (modo tolerante) o se eleva
    DataSourceError con el resumen (strict=True).
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

from .errors import DataSourceError, ValidationError
from .models import (
    Category, Donor, DonorKind, EventInfo, Hub, HubKind, Lot, LotStatus,
    Municipality, Road, RoadStatus, check_lot_temporal,
)

Row = Mapping[str, Any]


@dataclass(frozen=True)
class RowError:
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


@dataclass
class Dataset:
    event: EventInfo
    donors: dict[str, Donor] = field(default_factory=dict)
    hubs: dict[str, Hub] = field(default_factory=dict)
    municipalities: dict[str, Municipality] = field(default_factory=dict)
    roads: list[Road] = field(default_factory=list)
    lots: dict[str, Lot] = field(default_factory=dict)
    errors: list[RowError] = field(default_factory=list)


# ---------------------------------------------------------------- campos
def _text(row: Row, key: str) -> str:
    v = row.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"campo '{key}' vacío o ausente")
    return str(v).strip()


def _int(row: Row, key: str) -> int:
    v = row.get(key)
    if isinstance(v, bool):
        raise ValidationError(f"campo '{key}': se esperaba entero")
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    try:
        return int(_text(row, key))
    except ValueError:
        raise ValidationError(f"campo '{key}': '{v}' no es un entero válido") from None


def _float(row: Row, key: str) -> float:
    v = row.get(key)
    if isinstance(v, bool):
        raise ValidationError(f"campo '{key}': se esperaba número")
    try:
        x = float(v) if isinstance(v, (int, float)) else float(_text(row, key))
    except ValueError:
        raise ValidationError(f"campo '{key}': '{v}' no es numérico") from None
    if not math.isfinite(x):
        raise ValidationError(f"campo '{key}': valor no finito")
    return x


def _date(row: Row, key: str, optional: bool = False) -> date | None:
    v = row.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        if optional:
            return None
        raise ValidationError(f"campo '{key}' vacío o ausente")
    try:
        return date.fromisoformat(str(v).strip())
    except ValueError:
        raise ValidationError(f"campo '{key}': '{v}' no es fecha ISO (AAAA-MM-DD)") from None


def _enum(row: Row, key: str, cls):
    raw = _text(row, key).upper()
    try:
        return cls(raw)
    except ValueError:
        valid = ", ".join(e.value for e in cls)
        raise ValidationError(f"campo '{key}': '{raw}' inválido (válidos: {valid})") from None


def _bool(row: Row, key: str) -> bool:
    v = row.get(key)
    if isinstance(v, bool):
        return v
    s = _text(row, key).lower()
    if s in ("1", "true", "si", "sí", "yes"):
        return True
    if s in ("0", "false", "no"):
        return False
    raise ValidationError(f"campo '{key}': '{v}' no es booleano")


# ---------------------------------------------------------------- parsers
def parse_donor(row: Row) -> Donor:
    return Donor(_text(row, "donor_id"), _text(row, "name"), _enum(row, "kind", DonorKind), _text(row, "origin"))


def parse_hub(row: Row) -> Hub:
    return Hub(
        _text(row, "hub_id"), _text(row, "name"), _text(row, "department"), _enum(row, "kind", HubKind),
        _float(row, "lat"), _float(row, "lon"), _float(row, "capacity_m3"),
    )


def parse_municipality(row: Row) -> Municipality:
    needs = tuple((c, _int(row, f"need_{c.value.lower()}")) for c in Category)
    return Municipality(
        _text(row, "muni_id"), _text(row, "name"), _text(row, "department"), _text(row, "zone"),
        _int(row, "population"), _float(row, "lat"), _float(row, "lon"), _int(row, "urgency"),
        _int(row, "injured"), _int(row, "dead"), _int(row, "missing"), _int(row, "displaced"),
        _int(row, "damaged_homes"), needs,
    )


def parse_road(row: Row) -> Road:
    return Road(_text(row, "a"), _text(row, "b"), _float(row, "km"), _float(row, "speed_kmh"),
                _enum(row, "status", RoadStatus))


def parse_lot(row: Row) -> Lot:
    quantity = _int(row, "quantity")
    avail_raw = row.get("available")
    available = quantity if avail_raw in (None, "") else _int(row, "available")
    status_raw = row.get("status")
    status = LotStatus.AVAILABLE if status_raw in (None, "") else _enum(row, "status", LotStatus)
    return Lot(
        lot_id=_text(row, "lot_id"), donor_id=_text(row, "donor_id"), category=_enum(row, "category", Category),
        description=_text(row, "description"), quantity=quantity, unit=_text(row, "unit"),
        weight_kg=_float(row, "weight_kg"), volume_m3=_float(row, "volume_m3"), hub_id=_text(row, "hub_id"),
        received=_date(row, "received"), expiry=_date(row, "expiry", optional=True),
        cold_chain=_bool(row, "cold_chain"), available=available, status=status,
    )


LOT_FIELDS = ["lot_id", "donor_id", "category", "description", "quantity", "unit", "weight_kg", "volume_m3",
              "hub_id", "received", "expiry", "cold_chain", "available", "status"]


# ---------------------------------------------------------------- lectura cruda
def read_rows(path: Path | str) -> list[tuple[int, dict[str, Any]]]:
    """Devuelve (número de línea/posición, fila). Lanza DataSourceError ante fallas de I/O."""
    p = Path(path)
    try:
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text(encoding="utf-8-sig"))
            if not isinstance(data, list):
                raise DataSourceError(f"{p.name}: se esperaba una lista JSON de objetos")
            return [(i + 1, r if isinstance(r, dict) else {"__invalid__": r}) for i, r in enumerate(data)]
        out: list[tuple[int, dict[str, Any]]] = []
        with p.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise DataSourceError(f"{p.name}: archivo vacío o sin encabezado")
            for row in reader:
                if None in row:
                    row = {"__invalid__": "demasiados campos"}
                elif any(v is None for v in row.values()):
                    row = {**row, "__invalid__": "campos faltantes en la fila"}
                out.append((reader.line_num, row))
        return out
    except DataSourceError:
        raise
    except json.JSONDecodeError as e:
        raise DataSourceError(f"{p.name}: JSON mal formado ({e.msg}, línea {e.lineno})") from e
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise DataSourceError(f"{p.name}: no se pudo leer ({e})") from e


def load_table(path: Path | str, parser: Callable[[Row], Any], id_attr: str):
    """Parsea una tabla; devuelve (lista de (línea, objeto), errores)."""
    name = Path(path).name
    items: list[tuple[int, Any]] = []
    errors: list[RowError] = []
    seen: set[str] = set()
    for line, row in read_rows(path):
        try:
            if "__invalid__" in row:
                raise ValidationError(f"registro mal estructurado: {row['__invalid__']}")
            obj = parser(row)
            key = getattr(obj, id_attr, None)
            if key is not None:
                if key in seen:
                    raise ValidationError(f"identificador duplicado '{key}'")
                seen.add(key)
            items.append((line, obj))
        except ValidationError as e:
            errors.append(RowError(name, line, str(e)))
    return items, errors


def load_event(path: Path | str) -> EventInfo:
    p = Path(path)
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return EventInfo(str(d["name"]), date.fromisoformat(d["event_date"]),
                         float(d["epicenter_lat"]), float(d["epicenter_lon"]), float(d["magnitude"]))
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        raise DataSourceError(f"{p.name}: evento inválido o ilegible ({e})") from e


def load_dataset(directory: Path | str, strict: bool = False, lots_file: str = "lots.csv") -> Dataset:
    d = Path(directory)
    ds = Dataset(event=load_event(d / "event.json"))

    def run(fname: str, parser, id_attr: str):
        items, errs = load_table(d / fname, parser, id_attr)
        ds.errors.extend(errs)
        return items

    for _, o in run("donors.csv", parse_donor, "donor_id"):
        ds.donors[o.donor_id] = o
    for _, o in run("hubs.csv", parse_hub, "hub_id"):
        ds.hubs[o.hub_id] = o
    for _, o in run("municipalities.csv", parse_municipality, "muni_id"):
        ds.municipalities[o.muni_id] = o
    nodes = set(ds.hubs) | set(ds.municipalities)
    for line, r in run("roads.csv", parse_road, "__none__"):
        if r.a in nodes and r.b in nodes:
            ds.roads.append(r)
        else:
            ds.errors.append(RowError("roads.csv", line, f"carretera con nodo inexistente ({r.a}, {r.b})"))
    for line, lot in run(lots_file, parse_lot, "lot_id"):
        try:
            if lot.donor_id not in ds.donors:
                raise ValidationError(f"donante inexistente '{lot.donor_id}'")
            if lot.hub_id not in ds.hubs:
                raise ValidationError(f"centro de acopio inexistente '{lot.hub_id}'")
            check_lot_temporal(lot, ds.event.event_date)
            ds.lots[lot.lot_id] = lot
        except ValidationError as e:
            ds.errors.append(RowError(lots_file, line, str(e)))
    if strict and ds.errors:
        resumen = "; ".join(str(e) for e in ds.errors[:5])
        raise DataSourceError(f"{len(ds.errors)} registros inválidos: {resumen}")
    return ds


# ---------------------------------------------------------------- serialización
def lot_to_dict(lot: Lot) -> dict[str, Any]:
    return {
        "lot_id": lot.lot_id, "donor_id": lot.donor_id, "category": lot.category.value,
        "description": lot.description, "quantity": lot.quantity, "unit": lot.unit,
        "weight_kg": lot.weight_kg, "volume_m3": lot.volume_m3, "hub_id": lot.hub_id,
        "received": lot.received.isoformat(), "expiry": lot.expiry.isoformat() if lot.expiry else "",
        "cold_chain": lot.cold_chain, "available": lot.available, "status": lot.status.value,
    }


def save_lots_csv(path: Path | str, lots) -> None:
    try:
        with Path(path).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=LOT_FIELDS)
            w.writeheader()
            for lot in lots:
                w.writerow(lot_to_dict(lot))
    except OSError as e:
        raise DataSourceError(f"{Path(path).name}: no se pudo escribir ({e})") from e


def save_lots_json(path: Path | str, lots) -> None:
    try:
        Path(path).write_text(
            json.dumps([lot_to_dict(x) for x in lots], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        raise DataSourceError(f"{Path(path).name}: no se pudo escribir ({e})") from e


def load_lots(path: Path | str) -> tuple[list[Lot], list[RowError]]:
    items, errs = load_table(path, parse_lot, "lot_id")
    return [o for _, o in items], errs
