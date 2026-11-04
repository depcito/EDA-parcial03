"""Respuestas analíticas a las preguntas del reto, calculadas sobre los datos cargados.

Uso:  python -m donaciones.analysis [--data data] [--out docs/RESULTADOS.md]
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from .io_data import load_dataset
from .models import Category, LotStatus, Municipality
from .system import DonationSystem, EXPIRY_ALERT_DAYS

COUNTS = ("injured", "dead", "missing", "displaced", "damaged_homes")


def impact_summary(munis: list[Municipality]) -> dict:
    tot = {f: sum(getattr(m, f) for m in munis) for f in COUNTS}
    pop = sum(m.population for m in munis)
    tot["population"] = pop
    tot["municipalities"] = len(munis)
    tot["affected_municipalities"] = sum(1 for m in munis if m.urgency >= 3)
    return tot


def group_ranking(munis: list[Municipality], attr: str) -> list[dict]:
    g: dict[str, list[Municipality]] = defaultdict(list)
    for m in munis:
        g[getattr(m, attr)].append(m)
    rows = []
    for name, ms in g.items():
        pop = sum(m.population for m in ms)
        row = {"name": name, "municipalities": len(ms), "population": pop,
               "high_urgency": sum(1 for m in ms if m.urgency >= 4)}
        row.update({f: sum(getattr(m, f) for m in ms) for f in COUNTS})
        w = 5 * row["dead"] + 3 * row["missing"] + 2 * row["injured"] + row["displaced"]
        row["severity"] = 1000.0 * w / pop
        row["injured_per_10k"] = 10000.0 * row["injured"] / pop
        rows.append(row)
    return sorted(rows, key=lambda r: -r["severity"])


def top_municipalities(munis, key: str, n: int = 10) -> list[Municipality]:
    if key == "severity":
        return sorted(munis, key=lambda m: -m.severity_index)[:n]
    return sorted(munis, key=lambda m: -getattr(m, key))[:n]


def donor_report(system: DonationSystem, n: int = 8) -> list[dict]:
    rows = []
    for d in system.donors.values():
        lots = [system.lots[i] for i in system._by_donor.get(d.donor_id, ())]
        rows.append({"donor": d.name, "kind": d.kind.value, "lots": len(lots),
                     "dispatched_lots": sum(1 for l in lots if l.available < l.quantity)})
    return sorted(rows, key=lambda r: -r["lots"])[:n]


def expiry_risk(system: DonationSystem) -> list:
    return system.expiring_between(system.today, system.today + timedelta(days=EXPIRY_ALERT_DAYS))


def _table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def render_markdown(system: DonationSystem, allocated: bool) -> str:
    munis = list(system.munis.values())
    s = impact_summary(munis)
    L: list[str] = []
    L.append("## 1. ¿Cuánta gente hay herida (y afectada)?")
    L.append(f"- **Heridos: {s['injured']:,}** · fallecidos: {s['dead']:,} · desaparecidos: {s['missing']:,} · "
             f"desplazados: {s['displaced']:,} · viviendas dañadas: {s['damaged_homes']:,}.")
    L.append(f"- {s['affected_municipalities']} de {s['municipalities']} municipios con urgencia >= 3 "
             f"(población total considerada: {s['population']:,}).\n")
    L.append("Municipios con más heridos (cifra absoluta):\n")
    L.append(_table(["Municipio", "Zona", "Heridos", "Fallecidos", "Desplazados", "Urgencia"],
                    [[m.name, m.zone, f"{m.injured:,}", f"{m.dead:,}", f"{m.displaced:,}", m.urgency]
                     for m in top_municipalities(munis, "injured", 8)]))
    L.append("\n## 2. ¿Qué zonas están más afectadas?")
    L.append("Índice de severidad = (5·fallecidos + 3·desaparecidos + 2·heridos + desplazados) por cada 1.000 habitantes.\n")
    L.append(_table(["Zona", "Municipios", "Heridos", "Heridos/10 mil hab.", "Fallecidos", "Desplazados", "Mun. urgencia>=4", "Severidad"],
                    [[r["name"], r["municipalities"], f"{r['injured']:,}", f"{r['injured_per_10k']:.1f}", f"{r['dead']:,}",
                      f"{r['displaced']:,}", r["high_urgency"], f"{r['severity']:.0f}"]
                     for r in group_ranking(munis, "zone")]))
    L.append("\nPor departamento:\n")
    L.append(_table(["Departamento", "Heridos", "Fallecidos", "Desplazados", "Severidad"],
                    [[r["name"], f"{r['injured']:,}", f"{r['dead']:,}", f"{r['displaced']:,}", f"{r['severity']:.0f}"]
                     for r in group_ranking(munis, "department")[:6]]))
    L.append("\nMunicipios más afectados en términos relativos (severidad per cápita):\n")
    L.append(_table(["Municipio", "Zona", "Severidad", "Heridos", "Urgencia"],
                    [[m.name, m.zone, f"{m.severity_index:.0f}", f"{m.injured:,}", m.urgency]
                     for m in top_municipalities(munis, "severity", 8)]))
    iso = system.isolated_municipalities()
    L.append("\n## 3. ¿Qué municipios están incomunicados?")
    if iso:
        L.append(f"{len(iso)} municipios sin ruta transitable desde ningún centro de acopio "
                 f"(población {sum(m.population for m in iso):,}, heridos {sum(m.injured for m in iso):,}):\n")
        L.append(_table(["Municipio", "Zona", "Población", "Heridos", "Urgencia"],
                        [[m.name, m.zone, f"{m.population:,}", f"{m.injured:,}", m.urgency] for m in iso]))
        L.append("\nRequieren puente aéreo o reapertura de vías; el despacho terrestre no puede atenderlos.")
    else:
        L.append("Todos los municipios tienen al menos una ruta transitable.")
    L.append("\n## 4. ¿Qué cubre la ayuda recibida frente a la necesidad?")
    L.append("Estado: " + ("tras ejecutar la asignación automática." if allocated else "antes de asignar.") + "\n")
    L.append(_table(["Categoría", "Lotes", "Recibido", "Disponible", "Despachado", "Vencido", "Necesidad total", "Necesidad pendiente", "Cobertura"],
                    [[r["category"], r["lots"], f"{r['received']:,}", f"{r['available']:,}", f"{r['dispatched']:,}",
                      f"{r['expired']:,}", f"{r['demand']:,}", f"{r['remaining_need']:,}", f"{100 * r['coverage']:.0f}%"]
                     for r in system.stock_balance()]))
    if allocated:
        pend = [r for r in system.dispatch_summary() if r["remaining"] > 0]
        by_m: dict[str, int] = defaultdict(int)
        crit = [r for r in pend if r["urgency"] >= 4]
        for r in crit:
            by_m[r["municipality"]] += 1
        L.append(f"\nMunicipios de urgencia >= 4 con necesidades sin cubrir: {len(by_m)} "
                 f"({', '.join(sorted(by_m)[:10])}{'…' if len(by_m) > 10 else ''}).")
    L.append("\n## 5. Alertas tempranas")
    alerts = system.alerts()
    L.append("\n".join(f"- **{a.level}** [{a.kind}] {a.message}" for a in alerts[:14]) or "Sin alertas.")
    if len(alerts) > 14:
        L.append(f"- … y {len(alerts) - 14} más.")
    L.append("\n## 6. Donantes con más lotes")
    L.append(_table(["Donante", "Tipo", "Lotes", "Lotes con despacho"],
                    [[r["donor"], r["kind"], r["lots"], r["dispatched_lots"]] for r in donor_report(system)]))
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--data", default=str(root / "data"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    ds = load_dataset(a.data)
    sys_ = DonationSystem(ds)
    before = render_markdown(sys_, allocated=False)
    rep = sys_.allocate()
    after = render_markdown(sys_, allocated=True)
    text = (f"# Resultados del análisis (datos sintéticos)\n\nEvento: {ds.event.name} · M{ds.event.magnitude} · "
            f"fecha simulada de corte: {sys_.today}\n\nAsignaciones generadas: {len(rep.allocations)} · "
            f"solicitudes sin atender (total o parcial): {len(rep.unserved)}\n\n"
            f"{after}\n\n---\n\n<details><summary>Estado antes de asignar</summary>\n\n"
            f"## 4.{before.split('## 4.')[1].split('## 5.')[0]}\n</details>\n")
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"Escrito {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
