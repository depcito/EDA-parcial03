from datetime import date, timedelta
from pathlib import Path

from donaciones.io_data import load_dataset
from donaciones.models import Category, Lot
from donaciones.system import DonationSystem

DATA = Path(__file__).resolve().parent.parent / "data"
EVENT = date(2026, 3, 1)


def make_system() -> DonationSystem:
    return DonationSystem(load_dataset(DATA, strict=True))


def make_lot(lot_id="L-T001", cat=Category.VIVERES, qty=100, hub="H-PEI", expiry_days=30, cold=False, donor="D-001",
             received=None):
    received = received or EVENT + timedelta(days=3)
    return Lot(lot_id=lot_id, donor_id=donor, category=cat, description="prueba", quantity=qty, unit="u",
               weight_kg=1.0, volume_m3=0.1, hub_id=hub, received=received,
               expiry=None if expiry_days is None else received + timedelta(days=expiry_days), cold_chain=cold)
