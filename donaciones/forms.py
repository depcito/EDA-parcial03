"""Validación del formulario de nueva donación (independiente de Tk, por lo que es probable)."""
from __future__ import annotations

from datetime import date

from .errors import ValidationError
from .models import CATEGORY_UNITS, Category, Lot, check_lot_temporal
from .system import DonationSystem


def _num(text: str, kind=float):
    try:
        return kind(text.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None


def validate_donation_form(system: DonationSystem, values: dict[str, str]) -> tuple[Lot | None, dict[str, str]]:
    """Devuelve (lote, {}) si es válido o (None, {campo: mensaje}) con todos los errores."""
    errors: dict[str, str] = {}
    v = {k: (x if isinstance(x, str) else str(x)) for k, x in values.items()}

    donor = v.get("donor_id", "").strip()
    if donor not in system.donors:
        errors["donor_id"] = "Seleccione un donante registrado"
    hub = v.get("hub_id", "").strip()
    if hub not in system.hubs:
        errors["hub_id"] = "Seleccione un centro de acopio"
    try:
        cat = Category(v.get("category", "").strip().upper())
    except ValueError:
        cat = None
        errors["category"] = "Seleccione una categoría"
    desc = v.get("description", "").strip()
    if not desc:
        errors["description"] = "La descripción es obligatoria"

    qty = _num(v.get("quantity", ""), int)
    if qty is None:
        errors["quantity"] = "Cantidad: ingrese un entero"
    elif qty <= 0:
        errors["quantity"] = "Cantidad: debe ser mayor que cero"
    weight = _num(v.get("weight_kg", "0") or "0")
    if weight is None or weight < 0:
        errors["weight_kg"] = "Peso: número >= 0"
    volume = _num(v.get("volume_m3", "0") or "0")
    if volume is None or volume < 0:
        errors["volume_m3"] = "Volumen: número >= 0"

    expiry = None
    raw_exp = v.get("expiry", "").strip()
    if raw_exp:
        try:
            expiry = date.fromisoformat(raw_exp)
        except ValueError:
            errors["expiry"] = "Caducidad: use AAAA-MM-DD"
    if cat in (Category.MEDICO, Category.VIVERES, Category.AGUA) and not raw_exp:
        errors.setdefault("expiry", "Esta categoría requiere fecha de caducidad")

    if errors:
        return None, errors
    lot_id = v.get("lot_id", "").strip() or _next_id(system)
    try:
        lot = Lot(lot_id=lot_id, donor_id=donor, category=cat, description=desc, quantity=qty,
                  unit=CATEGORY_UNITS[cat], weight_kg=weight, volume_m3=volume, hub_id=hub,
                  received=system.today, expiry=expiry, cold_chain=bool(v.get("cold_chain") in ("1", "true", "True")))
        check_lot_temporal(lot, system.event_date)
        if expiry is not None and expiry < system.today:
            raise ValidationError("Caducidad: el lote ya está vencido")
    except ValidationError as e:
        field = "expiry" if "aduc" in str(e) else "quantity"
        return None, {field: str(e)}
    return lot, {}


def _next_id(system: DonationSystem) -> str:
    n = len(system.lots) + 1
    while f"L-{n:04d}" in system.lots:
        n += 1
    return f"L-{n:04d}"
