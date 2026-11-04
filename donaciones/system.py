"""Lógica de negocio: registro, búsqueda, asignación por triaje, informes y alertas."""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Iterable

from .errors import DonationError
from .estructuras import AVLTree, Graph, MinMaxHeap
from .io_data import Dataset
from .models import (
    Category, Lot, LotStatus, Municipality, RoadStatus, check_lot_temporal, haversine_km,
)

COLD_CHAIN_MAX_HOURS = 12.0
EXPIRY_ALERT_DAYS = 7
MAX_SPEED_KMH = 80.0
FAR_FUTURE_DAYS = 10**6


@dataclass(frozen=True)
class Allocation:
    alloc_id: int
    lot_id: str
    hub_id: str
    muni_id: str
    category: Category
    quantity: int
    weight_kg: float
    volume_m3: float
    eta_hours: float
    route: tuple[str, ...]


@dataclass(frozen=True)
class Request:
    muni_id: str
    category: Category
    quantity: int


@dataclass(frozen=True)
class Alert:
    level: str  # CRITICO | ALERTA
    kind: str
    message: str


@dataclass
class AllocationReport:
    allocations: list[Allocation] = field(default_factory=list)
    unserved: list[tuple[Request, str]] = field(default_factory=list)


class DonationSystem:
    def __init__(self, dataset: Dataset, today: date | None = None) -> None:
        self._lock = threading.RLock()
        self.event_date = dataset.event.event_date
        self.today = today or self.event_date + timedelta(days=3)
        self.donors = dict(dataset.donors)
        self.hubs = dict(dataset.hubs)
        self.munis = dict(dataset.municipalities)
        self.roads = list(dataset.roads)
        self.lots: dict[str, Lot] = {}
        self.allocations: list[Allocation] = []
        self._received: dict[tuple[str, Category], int] = {}
        # índices: hash maps + árboles AVL
        self._by_hub_cat: dict[tuple[str, Category], AVLTree] = {}  # FEFO por centro y categoría
        self._by_expiry = AVLTree()  # (fecha, lot_id) de lotes disponibles con caducidad
        self._funds = AVLTree()  # (monto, lot_id) de aportes económicos disponibles
        self._by_category: dict[Category, set[str]] = {c: set() for c in Category}
        self._by_donor: dict[str, set[str]] = {}
        self._next_alloc = 1
        self.graph = Graph()
        self._coords = {h.hub_id: (h.lat, h.lon) for h in self.hubs.values()}
        self._coords.update({m.muni_id: (m.lat, m.lon) for m in self.munis.values()})
        self._route_cache: dict[str, tuple[dict, dict]] = {}
        self._rebuild_graph()
        for lot in dataset.lots.values():
            self._store(lot)
        self._expire()

    # ------------------------------------------------------------ grafo
    def _rebuild_graph(self) -> None:
        g = Graph()
        for n in self._coords:
            g.add_node(n)
        for r in self.roads:
            if r.status is not RoadStatus.CLOSED:
                g.add_edge(r.a, r.b, r.hours)
        self.graph = g
        self._route_cache.clear()

    def heuristic(self, u: str, v: str) -> float:
        """Admisible: distancia geodésica / velocidad máxima (las carreteras reales son más largas y lentas)."""
        return haversine_km(*self._coords[u], *self._coords[v]) / MAX_SPEED_KMH

    def set_road_status(self, a: str, b: str, status: RoadStatus) -> None:
        with self._lock:
            found = False
            for i, r in enumerate(self.roads):
                if {r.a, r.b} == {a, b}:
                    self.roads[i] = replace(r, status=status)
                    found = True
            if not found:
                raise DonationError(f"no existe carretera {a}-{b}")
            self._rebuild_graph()

    def route(self, hub_id: str, muni_id: str, algorithm: str = "dijkstra"):
        """(horas, ruta hub->municipio). horas=inf y ruta vacía si no hay vía transitable."""
        with self._lock:
            if hub_id not in self.hubs or muni_id not in self.munis:
                raise DonationError("origen o destino desconocido")
            if algorithm == "astar":
                cost, path, _ = self.graph.astar(hub_id, muni_id, self.heuristic)
                return cost, path
            return self.graph.shortest_path(hub_id, muni_id)

    def _routes_from(self, muni_id: str):
        if muni_id not in self._route_cache:
            self._route_cache[muni_id] = self.graph.dijkstra(muni_id)
        return self._route_cache[muni_id]

    def isolated_municipalities(self) -> list[Municipality]:
        with self._lock:
            ok = self.graph.reachable_from(self.hubs)
            return sorted((m for m in self.munis.values() if m.muni_id not in ok), key=lambda m: m.name)

    # ------------------------------------------------------------ índices
    def _tree(self, hub_id: str, cat: Category) -> AVLTree:
        return self._by_hub_cat.setdefault((hub_id, cat), AVLTree())

    def _index(self, lot: Lot) -> None:
        self._tree(lot.hub_id, lot.category).insert((lot.shelf_key.toordinal(), lot.lot_id), lot.lot_id)
        if lot.expiry is not None:
            self._by_expiry.insert((lot.expiry.toordinal(), lot.lot_id), lot.lot_id)
        if lot.is_funds:
            self._funds.insert((lot.quantity, lot.lot_id), lot.lot_id)

    def _unindex(self, lot: Lot) -> None:
        self._tree(lot.hub_id, lot.category).remove((lot.shelf_key.toordinal(), lot.lot_id))
        if lot.expiry is not None:
            self._by_expiry.remove((lot.expiry.toordinal(), lot.lot_id))
        if lot.is_funds:
            self._funds.remove((lot.quantity, lot.lot_id))

    def _store(self, lot: Lot) -> None:
        self.lots[lot.lot_id] = lot
        self._by_category[lot.category].add(lot.lot_id)
        self._by_donor.setdefault(lot.donor_id, set()).add(lot.lot_id)
        if lot.status is LotStatus.AVAILABLE and lot.available > 0:
            self._index(lot)

    # ------------------------------------------------------------ registro
    def register_donation(self, lot: Lot) -> Lot:
        with self._lock:
            if lot.lot_id in self.lots:
                raise DonationError(f"el lote {lot.lot_id} ya existe")
            if lot.donor_id not in self.donors:
                raise DonationError(f"donante desconocido: {lot.donor_id}")
            if lot.hub_id not in self.hubs:
                raise DonationError(f"centro de acopio desconocido: {lot.hub_id}")
            if lot.quantity <= 0:
                raise DonationError("la cantidad debe ser mayor que cero")
            if lot.status is not LotStatus.AVAILABLE or lot.available != lot.quantity:
                raise DonationError("un lote nuevo debe ingresar disponible y completo")
            check_lot_temporal(lot, self.event_date)
            if lot.expiry is not None and lot.expiry < self.today:
                raise DonationError(f"el lote {lot.lot_id} ya está vencido")
            self._store(lot)
            return lot

    # ------------------------------------------------------------ búsqueda
    def get_lot(self, lot_id: str) -> Lot | None:
        with self._lock:
            return self.lots.get(lot_id)

    def expiring_between(self, d1: date, d2: date) -> list[Lot]:
        """Lotes disponibles con caducidad en [d1, d2], vía AVL: O(log n + k)."""
        with self._lock:
            lo, hi = (d1.toordinal(), ""), (d2.toordinal(), "￿")
            return [self.lots[v] for _, v in self._by_expiry.range(lo, hi)]

    def funds_between(self, min_cop: int, max_cop: int) -> list[Lot]:
        with self._lock:
            lo, hi = (min_cop, ""), (max_cop, "￿")
            return [self.lots[v] for _, v in self._funds.range(lo, hi)]

    def search(self, *, category: Category | None = None, hub_id: str | None = None,
               donor_id: str | None = None, expiring_within_days: int | None = None,
               cold_chain: bool | None = None, only_available: bool = True) -> list[Lot]:
        """Búsqueda multinivel: elige el índice más selectivo y filtra el resto. Orden FEFO."""
        with self._lock:
            if expiring_within_days is not None:
                cand: Iterable[Lot] = self.expiring_between(self.today, self.today + timedelta(days=expiring_within_days))
            elif hub_id and category:
                cand = (self.lots[v] for _, v in self._tree(hub_id, category).items())
            elif donor_id:
                cand = (self.lots[i] for i in self._by_donor.get(donor_id, ()))
            elif category:
                cand = (self.lots[i] for i in self._by_category[category])
            else:
                cand = self.lots.values()
            out = [
                l for l in cand
                if (category is None or l.category is category) and (hub_id is None or l.hub_id == hub_id)
                and (donor_id is None or l.donor_id == donor_id) and (cold_chain is None or l.cold_chain == cold_chain)
                and (not only_available or (l.status is LotStatus.AVAILABLE and l.available > 0))
            ]
            return sorted(out, key=lambda l: (l.shelf_key, l.lot_id))

    # ------------------------------------------------------------ vencimientos
    def set_today(self, today: date) -> None:
        with self._lock:
            self.today = today
            self._expire()

    def _expire(self) -> None:
        limit = (self.today.toordinal() - 1, "￿")
        for _, lot_id in list(self._by_expiry.range(None, limit)):
            lot = self.lots[lot_id]
            self._unindex(lot)
            self.lots[lot_id] = replace(lot, status=LotStatus.EXPIRED)

    # ------------------------------------------------------------ asignación
    def received(self, muni_id: str, cat: Category) -> int:
        return self._received.get((muni_id, cat), 0)

    def unmet(self, muni: Municipality, cat: Category) -> int:
        return max(0, muni.need(cat) - self.received(muni.muni_id, cat))

    def _shelf_days(self, cat: Category) -> int:
        best = FAR_FUTURE_DAYS
        for h in self.hubs:
            t = self._by_hub_cat.get((h, cat))
            if t:
                k, _ = t.min_item()
                best = min(best, max(0, k[0] - self.today.toordinal()))
        return best

    def build_queue(self) -> MinMaxHeap:
        """Cola de triaje: mayor urgencia, luego vida útil más corta, luego mayor severidad per cápita."""
        heap: MinMaxHeap = MinMaxHeap()
        shelf = {c: self._shelf_days(c) for c in Category}
        for m in self.munis.values():
            for cat in Category:
                q = self.unmet(m, cat)
                if q > 0:
                    heap.push((-m.urgency, shelf[cat], -m.severity_index, m.muni_id, cat.value), Request(m.muni_id, cat, q))
        return heap

    def queue_preview(self, n: int = 20) -> list[Request]:
        with self._lock:
            heap = self.build_queue()
            return [heap.pop_min()[1] for _ in range(min(n, len(heap)))]

    def allocate(self) -> AllocationReport:
        with self._lock:
            self._expire()
            report = AllocationReport()
            heap = self.build_queue()
            while heap:
                _, req = heap.pop_min()
                self._fulfil(req, report)
            return report

    def _fulfil(self, req: Request, report: AllocationReport) -> None:
        dist, prev = self._routes_from(req.muni_id)
        hubs = sorted((dist[h], h) for h in self.hubs if h in dist)
        if not hubs:
            report.unserved.append((req, "AISLADO: sin vía transitable desde ningún centro de acopio"))
            return
        remaining, skipped_cold = req.quantity, False
        for hours, hub in hubs:
            if remaining <= 0:
                break
            tree = self._by_hub_cat.get((hub, req.category))
            if not tree:
                continue
            picks: list[tuple[Lot, int]] = []
            need = remaining
            for _, lot_id in tree.items():  # FEFO: caducidad más próxima primero
                lot = self.lots[lot_id]
                if lot.cold_chain and hours > COLD_CHAIN_MAX_HOURS:
                    skipped_cold = True
                    continue
                take = min(lot.available, need)
                picks.append((lot, take))
                need -= take
                if need <= 0:
                    break
            route = tuple(reversed(Graph.path_from(prev, req.muni_id, hub)))
            for lot, take in picks:
                self._commit(lot, take, hours, route, req.muni_id, report)
            remaining = need
        if remaining > 0:
            why = "CADENA DE FRÍO: ruta superior al máximo permitido" if skipped_cold else "STOCK INSUFICIENTE"
            report.unserved.append((replace(req, quantity=remaining), why))

    def _commit(self, lot: Lot, take: int, hours: float, route: tuple[str, ...], muni_id: str,
                report: AllocationReport) -> None:
        self._unindex(lot)
        new = lot.take(take)
        self.lots[lot.lot_id] = new
        if new.available > 0:
            self._index(new)
        frac = take / lot.quantity
        alloc = Allocation(self._next_alloc, lot.lot_id, lot.hub_id, muni_id, lot.category, take,
                           round(lot.weight_kg * frac, 3), round(lot.volume_m3 * frac, 5), hours, route)
        self._next_alloc += 1
        self.allocations.append(alloc)
        report.allocations.append(alloc)
        key = (muni_id, lot.category)
        self._received[key] = self._received.get(key, 0) + take

    # ------------------------------------------------------------ informes
    def stock_balance(self) -> list[dict]:
        with self._lock:
            rows = []
            for cat in Category:
                ids = [self.lots[i] for i in self._by_category[cat]]
                received = sum(l.quantity for l in ids)
                avail = sum(l.available for l in ids if l.status is LotStatus.AVAILABLE)
                expired = sum(l.available for l in ids if l.status is LotStatus.EXPIRED)
                dispatched = sum(l.quantity - l.available for l in ids)
                demand = sum(m.need(cat) for m in self.munis.values())
                remaining = sum(self.unmet(m, cat) for m in self.munis.values())
                rows.append({"category": cat.value, "lots": len(ids), "received": received, "available": avail,
                             "dispatched": dispatched, "expired": expired, "demand": demand,
                             "remaining_need": remaining,
                             "coverage": (demand - remaining) / demand if demand else 1.0})
            return rows

    def dispatch_summary(self) -> list[dict]:
        with self._lock:
            out = []
            for m in sorted(self.munis.values(), key=lambda m: (-m.urgency, -m.severity_index)):
                for cat in Category:
                    need = m.need(cat)
                    if need:
                        got = self.received(m.muni_id, cat)
                        out.append({"muni_id": m.muni_id, "municipality": m.name, "urgency": m.urgency,
                                    "category": cat.value, "need": need, "received": got, "remaining": need - got})
            return out

    def hub_load(self) -> dict[str, float]:
        """Volumen (m3) disponible por centro."""
        with self._lock:
            load = {h: 0.0 for h in self.hubs}
            for l in self.lots.values():
                if l.status is LotStatus.AVAILABLE and l.quantity:
                    load[l.hub_id] += l.volume_m3 * l.available / l.quantity
            return load

    def alerts(self) -> list[Alert]:
        with self._lock:
            out: list[Alert] = []
            for row in self.stock_balance():
                rem, avail = row["remaining_need"], row["available"]
                if rem > 0 and avail < rem:
                    lvl = "CRITICO" if avail < 0.5 * rem else "ALERTA"
                    out.append(Alert(lvl, "DESABASTECIMIENTO",
                                     f"{row['category']}: disponible {avail:,} < necesidad pendiente {rem:,}"))
            soon = self.expiring_between(self.today, self.today + timedelta(days=EXPIRY_ALERT_DAYS))
            for l in soon:
                out.append(Alert("ALERTA", "VENCIMIENTO",
                                 f"{l.lot_id} {l.description}: vence {l.expiry} ({l.available:,} {l.unit} en {l.hub_id})"))
            for m in self.isolated_municipalities():
                pend = sum(self.unmet(m, c) for c in Category)
                if pend > 0:
                    out.append(Alert("CRITICO", "AISLAMIENTO",
                                     f"{m.name} sin vía transitable: requiere puente aéreo (urgencia {m.urgency})"))
            for h, vol in self.hub_load().items():
                if vol > self.hubs[h].capacity_m3:
                    out.append(Alert("ALERTA", "CAPACIDAD", f"{self.hubs[h].name}: {vol:,.0f} m3 supera capacidad"))
            order = {"CRITICO": 0, "ALERTA": 1}
            return sorted(out, key=lambda a: order[a.level])
