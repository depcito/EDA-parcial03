"""Panel de control (Tkinter). Las operaciones largas corren en hilos para no congelar la UI."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import timedelta
from tkinter import messagebox, ttk
from typing import Callable

from . import analysis
from .errors import DonationError
from .forms import validate_donation_form
from .models import CATEGORY_UNITS, Category, RoadStatus
from .system import DonationSystem

URG_COLORS = {5: "#b71c1c", 4: "#e65100", 3: "#f9a825", 2: "#7cb342", 1: "#9e9e9e"}
ROAD_COLORS = {RoadStatus.OPEN: "#9aa5b1", RoadStatus.RESTRICTED: "#f57c00", RoadStatus.CLOSED: "#d32f2f"}


def _tree(parent, columns: list[tuple[str, int]], height: int = 12) -> ttk.Treeview:
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tv = ttk.Treeview(frame, columns=[c for c, _ in columns], show="headings", height=height)
    for c, w in columns:
        tv.heading(c, text=c)
        tv.column(c, width=w, anchor="w")
    sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return tv


def fill(tv: ttk.Treeview, rows: list[tuple], tags: list[str] | None = None) -> None:
    tv.delete(*tv.get_children())
    for i, r in enumerate(rows):
        tv.insert("", "end", values=r, tags=(tags[i],) if tags else ())


class App(tk.Tk):
    def __init__(self, system: DonationSystem) -> None:
        super().__init__()
        self.system = system
        self.title("Gestión de donaciones post-sismo — Panel de operaciones")
        self.geometry("1180x720")
        self._results: queue.Queue = queue.Queue()
        self._build()
        self._poll_id = self.after(100, self._poll)
        self.refresh_all()

    # ---------------------------------------------------------- asincronía
    def run_async(self, work: Callable, done: Callable, busy: ttk.Progressbar | None = None) -> None:
        if busy:
            busy.start(12)

        def target():
            try:
                res = ("ok", work())
            except Exception as e:  # noqa: BLE001 - se informa en la UI
                res = ("err", e)
            self._results.put((done, busy, res))

        threading.Thread(target=target, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                done, busy, res = self._results.get_nowait()
                if busy:
                    busy.stop()
                if res[0] == "ok":
                    done(res[1])
                else:
                    self.status.set(f"Error: {res[1]}")
                    messagebox.showerror("Error", str(res[1]), parent=self)
        except queue.Empty:
            pass
        self._poll_id = self.after(100, self._poll)

    def destroy(self) -> None:
        try:
            self.after_cancel(self._poll_id)
        except (tk.TclError, AttributeError):
            pass
        super().destroy()

    # ---------------------------------------------------------- construcción
    def _build(self) -> None:
        self.status = tk.StringVar(value="Listo")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.tabs = {}
        for name, builder in [("Panel", self._tab_dashboard), ("Inventario", self._tab_inventory),
                              ("Nueva donación", self._tab_register), ("Despacho", self._tab_dispatch),
                              ("Rutas", self._tab_routes), ("Análisis", self._tab_analysis)]:
            f = ttk.Frame(nb, padding=8)
            nb.add(f, text=name)
            self.tabs[name] = f
            builder(f)
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def _tab_dashboard(self, f) -> None:
        self.kpis = {}
        row = ttk.Frame(f)
        row.pack(fill="x")
        for key, label in [("injured", "Heridos"), ("dead", "Fallecidos"), ("displaced", "Desplazados"),
                           ("isolated", "Municipios aislados"), ("lots", "Lotes disponibles"), ("alloc", "Asignaciones")]:
            box = ttk.LabelFrame(row, text=label, padding=8)
            box.pack(side="left", expand=True, fill="x", padx=3)
            v = tk.StringVar(value="-")
            ttk.Label(box, textvariable=v, font=("Segoe UI", 16, "bold")).pack()
            self.kpis[key] = v
        ttk.Label(f, text="Alertas tempranas (críticas primero)", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.alert_tv = _tree(f, [("Nivel", 80), ("Tipo", 140), ("Mensaje", 800)], 8)
        self.alert_tv.tag_configure("CRITICO", foreground="#b71c1c")
        self.alert_tv.tag_configure("ALERTA", foreground="#e65100")
        ttk.Label(f, text="Balance de stock por categoría", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.bal_tv = _tree(f, [("Categoría", 100), ("Recibido", 120), ("Disponible", 120), ("Despachado", 120),
                                ("Vencido", 90), ("Necesidad pendiente", 150), ("Cobertura", 90)], 7)
        ttk.Button(f, text="Actualizar", command=self.refresh_all).pack(anchor="e", pady=4)

    def _tab_inventory(self, f) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x", pady=(0, 6))
        self.inv_cat = ttk.Combobox(bar, values=["(todas)"] + [c.value for c in Category], state="readonly", width=12)
        self.inv_cat.set("(todas)")
        self.inv_hub = ttk.Combobox(bar, values=["(todos)"] + list(self.system.hubs), state="readonly", width=10)
        self.inv_hub.set("(todos)")
        self.inv_days = ttk.Entry(bar, width=6)
        self.inv_id = ttk.Entry(bar, width=10)
        for lbl, w in [("Categoría", self.inv_cat), ("Centro", self.inv_hub), ("Vence en ≤ días", self.inv_days), ("ID lote", self.inv_id)]:
            ttk.Label(bar, text=lbl).pack(side="left", padx=(8, 2))
            w.pack(side="left")
        ttk.Button(bar, text="Buscar", command=self.search_inventory).pack(side="left", padx=8)
        self.inv_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.inv_count).pack(side="right")
        self.inv_tv = _tree(f, [("Lote", 80), ("Categoría", 90), ("Descripción", 300), ("Centro", 80), ("Disponible", 100),
                                ("Unidad", 80), ("Vence", 90), ("Frío", 50), ("Estado", 90)], 22)

    def search_inventory(self) -> None:
        raw = self.inv_days.get().strip()
        days = None
        if raw:
            if not raw.isdigit():
                self.status.set("Días: ingrese un entero >= 0")
                self.inv_days.configure(foreground="red")
                return
            days = int(raw)
        self.inv_days.configure(foreground="black")
        lot_id = self.inv_id.get().strip()
        if lot_id:
            lot = self.system.get_lot(lot_id)
            lots = [lot] if lot else []
        else:
            cat = self.inv_cat.get()
            hub = self.inv_hub.get()
            lots = self.system.search(category=None if cat.startswith("(") else Category(cat),
                                      hub_id=None if hub.startswith("(") else hub, expiring_within_days=days)
        fill(self.inv_tv, [(l.lot_id, l.category.value, l.description, l.hub_id, f"{l.available:,}", l.unit,
                            l.expiry or "—", "sí" if l.cold_chain else "", l.status.value) for l in lots[:2000]])
        self.inv_count.set(f"{len(lots):,} lotes")

    def _tab_register(self, f) -> None:
        self.form_vars: dict[str, tk.StringVar] = {}
        self.form_err: dict[str, ttk.Label] = {}
        grid = ttk.Frame(f)
        grid.pack(anchor="nw")
        donors = [f"{d.donor_id} · {d.name}" for d in self.system.donors.values()]
        fields = [("donor_id", "Donante", donors), ("category", "Categoría", [c.value for c in Category]),
                  ("description", "Descripción", None), ("quantity", "Cantidad", None), ("weight_kg", "Peso total (kg)", None),
                  ("volume_m3", "Volumen total (m³)", None), ("hub_id", "Centro de acopio", list(self.system.hubs)),
                  ("expiry", "Caducidad (AAAA-MM-DD)", None)]
        for r, (key, label, opts) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="e", padx=4, pady=3)
            var = tk.StringVar()
            w = ttk.Combobox(grid, textvariable=var, values=opts, state="readonly", width=48) if opts else ttk.Entry(grid, textvariable=var, width=50)
            w.grid(row=r, column=1, pady=3)
            err = ttk.Label(grid, text="", foreground="#b71c1c")
            err.grid(row=r, column=2, sticky="w", padx=6)
            self.form_vars[key], self.form_err[key] = var, err
        self.cold_var = tk.BooleanVar()
        ttk.Checkbutton(grid, text="Requiere cadena de frío", variable=self.cold_var).grid(row=len(fields), column=1, sticky="w")
        ttk.Button(grid, text="Registrar donación", command=self.submit_donation).grid(row=len(fields) + 1, column=1, sticky="w", pady=10)
        self.form_msg = tk.StringVar()
        ttk.Label(f, textvariable=self.form_msg, font=("Segoe UI", 10, "bold")).pack(anchor="w")

    def submit_donation(self) -> None:
        values = {k: v.get() for k, v in self.form_vars.items()}
        values["donor_id"] = values["donor_id"].split(" · ")[0]
        values["cold_chain"] = "1" if self.cold_var.get() else "0"
        lot, errors = validate_donation_form(self.system, values)
        for k, lbl in self.form_err.items():
            lbl.configure(text=errors.get(k, ""))
        if errors:
            self.form_msg.set("Corrija los campos marcados en rojo")
            return
        try:
            self.system.register_donation(lot)
        except DonationError as e:
            self.form_msg.set(str(e))
            return
        self.form_msg.set(f"Lote {lot.lot_id} registrado ({lot.quantity:,} {lot.unit})")
        self.refresh_all()

    def _tab_dispatch(self, f) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar, text="Ejecutar asignación automática", command=self.run_allocation).pack(side="left")
        ttk.Button(bar, text="Ver cola de prioridad", command=self.show_queue).pack(side="left", padx=6)
        self.busy = ttk.Progressbar(bar, mode="indeterminate", length=180)
        self.busy.pack(side="left", padx=10)
        self.disp_msg = tk.StringVar()
        ttk.Label(bar, textvariable=self.disp_msg).pack(side="left")
        ttk.Label(f, text="Cola de triaje / asignaciones", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 2))
        self.disp_tv = _tree(f, [("Municipio", 160), ("Categoría", 90), ("Cantidad", 110), ("Centro origen", 90),
                                 ("ETA (h)", 70), ("Ruta", 520)], 14)
        ttk.Label(f, text="Sin atender / parcial", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(8, 2))
        self.unserved_tv = _tree(f, [("Municipio", 160), ("Categoría", 90), ("Pendiente", 110), ("Motivo", 600)], 6)

    def show_queue(self) -> None:
        reqs = self.system.queue_preview(40)
        fill(self.disp_tv, [(self.system.munis[r.muni_id].name, r.category.value, f"{r.quantity:,}", "", "", "") for r in reqs])
        self.disp_msg.set(f"Próximas {len(reqs)} solicitudes por prioridad")

    def run_allocation(self) -> None:
        self.disp_msg.set("Asignando…")
        self.run_async(self.system.allocate, self._allocation_done, self.busy)

    def _allocation_done(self, rep) -> None:
        names = {m.muni_id: m.name for m in self.system.munis.values()}
        fill(self.disp_tv, [(names[a.muni_id], a.category.value, f"{a.quantity:,}", a.hub_id, f"{a.eta_hours:.1f}",
                             " → ".join(names.get(n, n) for n in a.route)) for a in rep.allocations[:3000]])
        fill(self.unserved_tv, [(names[r.muni_id], r.category.value, f"{r.quantity:,}", why) for r, why in rep.unserved])
        self.disp_msg.set(f"{len(rep.allocations)} asignaciones · {len(rep.unserved)} solicitudes sin cubrir")
        self.refresh_all()

    def _tab_routes(self, f) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        names = {m.name: m.muni_id for m in self.system.munis.values()}
        self._muni_by_name = names
        self.route_hub = ttk.Combobox(bar, values=list(self.system.hubs), state="readonly", width=10)
        self.route_hub.set(next(iter(self.system.hubs)))
        self.route_muni = ttk.Combobox(bar, values=sorted(names), state="readonly", width=24)
        self.route_muni.set("Armenia")
        self.route_alg = ttk.Combobox(bar, values=["dijkstra", "astar"], state="readonly", width=9)
        self.route_alg.set("dijkstra")
        for lbl, w in [("Origen", self.route_hub), ("Destino", self.route_muni), ("Algoritmo", self.route_alg)]:
            ttk.Label(bar, text=lbl).pack(side="left", padx=(8, 2))
            w.pack(side="left")
        ttk.Button(bar, text="Calcular ruta", command=self.compute_route).pack(side="left", padx=8)
        self.route_msg = tk.StringVar()
        ttk.Label(bar, textvariable=self.route_msg).pack(side="left")
        self.canvas = tk.Canvas(f, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.canvas.pack(fill="both", expand=True, pady=6)
        self.canvas.bind("<Configure>", lambda e: self.draw_map())
        self._route_path: list[str] = []

    def _project(self, lat: float, lon: float):
        w, h = max(self.canvas.winfo_width(), 200), max(self.canvas.winfo_height(), 200)
        la0, la1, lo0, lo1 = 3.3, 6.4, -77.2, -74.9
        return 20 + (lon - lo0) / (lo1 - lo0) * (w - 40), 20 + (la1 - lat) / (la1 - la0) * (h - 40)

    def draw_map(self) -> None:
        c = self.canvas
        c.delete("all")
        s = self.system
        pos = {k: self._project(*v) for k, v in s._coords.items()}
        for r in s.roads:
            if r.a in pos and r.b in pos:
                c.create_line(*pos[r.a], *pos[r.b], fill=ROAD_COLORS[r.status], width=1, dash=(4, 3) if r.status is RoadStatus.CLOSED else ())
        for a, b in zip(self._route_path, self._route_path[1:]):
            c.create_line(*pos[a], *pos[b], fill="#1565c0", width=4)
        for m in s.munis.values():
            x, y = pos[m.muni_id]
            if 0 <= x <= c.winfo_width() and 0 <= y <= c.winfo_height():
                rad = 4 + m.urgency
                c.create_oval(x - rad, y - rad, x + rad, y + rad, fill=URG_COLORS[m.urgency], outline="")
                c.create_text(x + rad + 2, y, text=m.name, anchor="w", font=("Segoe UI", 7))
        for h in s.hubs.values():
            x, y = pos[h.hub_id]
            c.create_rectangle(x - 5, y - 5, x + 5, y + 5, fill="#1a237e", outline="")
            c.create_text(x, y - 10, text=h.hub_id, font=("Segoe UI", 7, "bold"), fill="#1a237e")
        c.create_text(10, c.winfo_height() - 10, anchor="sw", font=("Segoe UI", 8),
                      text="Círculos: municipios (color = urgencia) · Cuadros: centros · Rojo punteado: vía cerrada · Naranja: restringida · Azul: ruta")

    def compute_route(self) -> None:
        hub, muni = self.route_hub.get(), self._muni_by_name[self.route_muni.get()]
        cost, path = self.system.route(hub, muni, self.route_alg.get())
        self._route_path = path
        if not path:
            self.route_msg.set("Sin ruta transitable: requiere puente aéreo")
        else:
            self.route_msg.set(f"{cost:.1f} h · {len(path) - 1} tramos")
        self.draw_map()

    def _tab_analysis(self, f) -> None:
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        self.an_busy = ttk.Progressbar(bar, mode="indeterminate", length=160)
        ttk.Button(bar, text="Generar respuestas (heridos, zonas, aislamiento, cobertura)", command=self.run_analysis).pack(side="left")
        self.an_busy.pack(side="left", padx=10)
        self.an_text = tk.Text(f, wrap="word", font=("Consolas", 9))
        self.an_text.pack(fill="both", expand=True, pady=6)

    def run_analysis(self) -> None:
        allocated = bool(self.system.allocations)
        self.run_async(lambda: analysis.render_markdown(self.system, allocated), self._analysis_done, self.an_busy)

    def _analysis_done(self, text: str) -> None:
        self.an_text.delete("1.0", "end")
        self.an_text.insert("1.0", text)

    # ---------------------------------------------------------- refresco
    def refresh_all(self) -> None:
        s = self.system
        munis = list(s.munis.values())
        self.kpis["injured"].set(f"{sum(m.injured for m in munis):,}")
        self.kpis["dead"].set(f"{sum(m.dead for m in munis):,}")
        self.kpis["displaced"].set(f"{sum(m.displaced for m in munis):,}")
        self.kpis["isolated"].set(str(len(s.isolated_municipalities())))
        self.kpis["lots"].set(f"{len(s.search()):,}")
        self.kpis["alloc"].set(f"{len(s.allocations):,}")
        alerts = s.alerts()
        fill(self.alert_tv, [(a.level, a.kind, a.message) for a in alerts], [a.level for a in alerts])
        fill(self.bal_tv, [(r["category"], f"{r['received']:,}", f"{r['available']:,}", f"{r['dispatched']:,}", f"{r['expired']:,}",
                            f"{r['remaining_need']:,}", f"{100 * r['coverage']:.0f}%") for r in s.stock_balance()])
        self.search_inventory()
        self.status.set(f"Actualizado · fecha de corte {s.today}")


def run(data_dir: str) -> None:
    from .io_data import load_dataset

    ds = load_dataset(data_dir)
    app = App(DonationSystem(ds))
    if ds.errors:
        messagebox.showwarning("Datos", f"{len(ds.errors)} registros inválidos omitidos.\nPrimero: {ds.errors[0]}", parent=app)
    app.mainloop()
