"""Genera el conjunto de datos SINTÉTICO (determinista) en ../data.

Municipios reales de la zona cafetera/occidente con población y coordenadas
APROXIMADAS; el sismo, sus víctimas, las necesidades, los donantes y las
donaciones son ficticios. Uso:  python scripts/generar_datos.py
"""
import csv
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from donaciones.models import CATEGORY_UNITS, Category, haversine_km  # noqa: E402

SEED = 20260301
EVENT = date(2026, 3, 1)
EPI = (4.40, -75.75)

# (nombre, departamento, zona, población aprox., lat, lon)
MUNIS = [
    ("Armenia", "Quindío", "Quindío", 300000, 4.534, -75.681), ("Calarcá", "Quindío", "Quindío", 80000, 4.529, -75.641),
    ("Montenegro", "Quindío", "Quindío", 40000, 4.567, -75.752), ("Quimbaya", "Quindío", "Quindío", 35000, 4.623, -75.763),
    ("La Tebaida", "Quindío", "Quindío", 45000, 4.455, -75.789), ("Circasia", "Quindío", "Quindío", 30000, 4.618, -75.637),
    ("Salento", "Quindío", "Quindío", 8000, 4.637, -75.571), ("Filandia", "Quindío", "Quindío", 13000, 4.675, -75.659),
    ("Génova", "Quindío", "Quindío", 7000, 4.206, -75.790), ("Pijao", "Quindío", "Quindío", 6000, 4.331, -75.703),
    ("Córdoba (Quindío)", "Quindío", "Quindío", 5000, 4.393, -75.686), ("Buenavista", "Quindío", "Quindío", 3000, 4.357, -75.737),
    ("Pereira", "Risaralda", "Risaralda", 480000, 4.814, -75.696), ("Dosquebradas", "Risaralda", "Risaralda", 210000, 4.839, -75.673),
    ("Santa Rosa de Cabal", "Risaralda", "Risaralda", 75000, 4.868, -75.623), ("Marsella", "Risaralda", "Risaralda", 20000, 4.937, -75.743),
    ("Pueblo Rico", "Risaralda", "Risaralda", 13000, 5.218, -76.027), ("Belén de Umbría", "Risaralda", "Risaralda", 25000, 5.200, -75.866),
    ("Manizales", "Caldas", "Caldas", 450000, 5.070, -75.514), ("Chinchiná", "Caldas", "Caldas", 52000, 4.984, -75.607),
    ("Villamaría", "Caldas", "Caldas", 60000, 5.045, -75.516), ("Palestina", "Caldas", "Caldas", 18000, 5.019, -75.618),
    ("Neira", "Caldas", "Caldas", 24000, 5.166, -75.522),
    ("Cartago", "Valle del Cauca", "Norte del Valle", 140000, 4.746, -75.912), ("Zarzal", "Valle del Cauca", "Norte del Valle", 45000, 4.392, -76.071),
    ("Caicedonia", "Valle del Cauca", "Norte del Valle", 30000, 4.332, -75.828), ("Sevilla", "Valle del Cauca", "Norte del Valle", 45000, 4.269, -75.935),
    ("Alcalá", "Valle del Cauca", "Norte del Valle", 20000, 4.678, -75.784), ("Ulloa", "Valle del Cauca", "Norte del Valle", 5000, 4.704, -75.738),
    ("Tuluá", "Valle del Cauca", "Centro del Valle", 220000, 4.084, -76.195), ("Buga", "Valle del Cauca", "Centro del Valle", 120000, 3.900, -76.298),
    ("Palmira", "Valle del Cauca", "Centro del Valle", 310000, 3.540, -76.303), ("Cali", "Valle del Cauca", "Centro del Valle", 2200000, 3.452, -76.532),
    ("Buenaventura", "Valle del Cauca", "Pacífico", 430000, 3.880, -77.031),
    ("Ibagué", "Tolima", "Tolima", 540000, 4.438, -75.232), ("Cajamarca", "Tolima", "Tolima", 20000, 4.438, -75.428),
    ("Roncesvalles", "Tolima", "Tolima", 6000, 4.014, -75.605), ("Chaparral", "Tolima", "Tolima", 50000, 3.723, -75.484),
    ("Líbano", "Tolima", "Tolima", 40000, 4.921, -75.063),
    ("Medellín", "Antioquia", "Antioquia", 2600000, 6.244, -75.581), ("Rionegro", "Antioquia", "Antioquia", 140000, 6.155, -75.374),
    ("Andes", "Antioquia", "Antioquia", 45000, 5.657, -75.881), ("Jardín", "Antioquia", "Antioquia", 14000, 5.598, -75.819),
    ("Bogotá D.C.", "Bogotá D.C.", "Capital", 7900000, 4.711, -74.072),
    ("Barranquilla", "Atlántico", "Costa Caribe", 1300000, 10.964, -74.796),
]

# id, nombre, departamento, tipo, lat, lon, capacidad m3
HUBS = [
    ("H-BOG", "Aeropuerto El Dorado (Bogotá)", "Bogotá D.C.", "AEROPUERTO", 4.701, -74.147, 6000),
    ("H-MDE", "Aeropuerto de Rionegro (Antioquia)", "Antioquia", "AEROPUERTO", 6.164, -75.423, 3500),
    ("H-CLO", "Aeropuerto de Palmira (Valle)", "Valle del Cauca", "AEROPUERTO", 3.543, -76.381, 3500),
    ("H-BUN", "Puerto de Buenaventura", "Valle del Cauca", "PUERTO", 3.900, -77.060, 9000),
    ("H-BAQ", "Puerto de Barranquilla", "Atlántico", "PUERTO", 10.980, -74.770, 7000),
    ("H-PEI", "Acopio regional Pereira", "Risaralda", "ACOPIO", 4.806, -75.739, 2500),
    ("H-IBA", "Acopio regional Ibagué", "Tolima", "ACOPIO", 4.440, -75.200, 1800),
    ("H-MAN", "Acopio regional Manizales", "Caldas", "ACOPIO", 5.040, -75.470, 1500),
    ("H-AXM", "Acopio aeropuerto de Armenia", "Quindío", "ACOPIO", 4.453, -75.766, 1200),
]

DONOR_NAMES = [
    ("Fundación Sol Naciente", "ONG"), ("Alianza Humanitaria Andina", "ONG"), ("Corporación Agua Viva", "ONG"),
    ("Banco de Alimentos del Café", "ONG"), ("TransAndes Logística", "EMPRESA"), ("Farmacéutica Meridiano", "EMPRESA"),
    ("Constructora Cordillera", "EMPRESA"), ("Supermercados La Quinta", "EMPRESA"), ("Embotelladora Río Claro", "EMPRESA"),
    ("Gobierno Aliado Norte (cooperación)", "INTERNACIONAL"), ("Fondo Humanitario Atlántico", "INTERNACIONAL"),
    ("Misión Médica Sin Fronteras (simulada)", "INTERNACIONAL"), ("Cooperativa Cafetera del Occidente", "EMPRESA"),
    ("Gobernación Aliada 1", "GOBIERNO"), ("Gobernación Aliada 2", "GOBIERNO"), ("Alcaldía Solidaria", "GOBIERNO"),
    ("Colegio Los Pinos (campaña)", "ONG"), ("Universidad Solidaria (campaña)", "ONG"), ("Iglesia San Isidro (campaña)", "ONG"),
    ("Ciudadano anónimo 1", "PERSONA"), ("Ciudadano anónimo 2", "PERSONA"), ("Ciudadano anónimo 3", "PERSONA"),
    ("Empresa Textil Aurora", "EMPRESA"), ("Ferretería Industrial del Valle", "EMPRESA"),
]
DONOR_ORIGIN = ["Bogotá", "Medellín", "Cali", "Barranquilla", "Bucaramanga", "Cartagena", "Miami", "Madrid", "Ciudad de México"]

DESC = {
    Category.MEDICO: ["Kit de triaje y material quirúrgico", "Insumos médicos críticos", "Kit de curaciones", "Vacunas y biológicos (cadena de frío)"],
    Category.VIVERES: ["Ración no perecedera", "Paquete alimentario", "Pan y alimentos frescos", "Enlatados y granos"],
    Category.AGUA: ["Agua potable embolsada", "Agua embotellada", "Planta potabilizadora portátil (equivalente en litros)"],
    Category.REFUGIO: ["Kit de refugio (carpa y cobijas)", "Kit de emergencia familiar"],
    Category.RESCATE: ["Herramientas de rescate", "Equipo de excavación y apuntalamiento"],
    Category.FONDOS: ["Aporte económico para compras en zonas contiguas", "Transferencia humanitaria"],
}
UNIT_W = {Category.MEDICO: (1.8, 0.012), Category.VIVERES: (0.5, 0.0015), Category.AGUA: (1.0, 0.001),
          Category.REFUGIO: (7.0, 0.06), Category.RESCATE: (4.0, 0.03), Category.FONDOS: (0.0, 0.0)}
N_LOTS = {Category.MEDICO: 40, Category.VIVERES: 55, Category.AGUA: 45, Category.REFUGIO: 35, Category.RESCATE: 30, Category.FONDOS: 40}
COVERAGE = {Category.MEDICO: 0.55, Category.VIVERES: 0.90, Category.AGUA: 1.15, Category.REFUGIO: 0.70, Category.RESCATE: 0.80, Category.FONDOS: 0.85}
HUB_WEIGHT = {"H-BOG": 5, "H-MDE": 3, "H-CLO": 3, "H-BUN": 2, "H-BAQ": 2, "H-PEI": 3, "H-IBA": 1, "H-MAN": 1, "H-AXM": 1}


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def make_municipalities(rng):
    rows = []
    for i, (name, dept, zone, pop, lat, lon) in enumerate(MUNIS, 1):
        d = haversine_km(EPI[0], EPI[1], lat, lon)
        vul = rng.uniform(0.6, 1.5) * (1.3 if pop < 20000 else 1.0)
        injured = round(pop * 0.025 * math.exp(-d / 35) * vul)
        dead = round(injured * rng.uniform(0.08, 0.16))
        missing = round(injured * rng.uniform(0.02, 0.08))
        displaced = min(pop, round(pop * 0.15 * math.exp(-d / 40) * vul))
        homes = round(displaced / 3.6 * rng.uniform(0.8, 1.2))
        sev = 1000 * (5 * dead + 3 * missing + 2 * injured + displaced) / pop
        urgency = 5 if sev >= 150 else 4 if sev >= 70 else 3 if sev >= 25 else 2 if sev >= 6 else 1
        needs = {
            "medico": round(injured * 1.5 + dead * 0.2), "agua": displaced * 45, "viveres": displaced * 9,
            "refugio": math.ceil(displaced / 4), "rescate": homes // 8, "fondos": displaced * 200000,
        }
        row = {"muni_id": f"M-{i:03d}", "name": name, "department": dept, "zone": zone, "population": pop,
               "lat": lat, "lon": lon, "urgency": urgency, "injured": injured, "dead": dead, "missing": missing,
               "displaced": displaced, "damaged_homes": homes}
        row.update({f"need_{c.value.lower()}": needs[c.value.lower()] for c in Category})
        rows.append(row)
    return rows


def make_roads(rng, nodes):
    """k=3 vecinos más cercanos + unión de componentes; estado según cercanía al epicentro."""
    ids = list(nodes)
    edges = {}

    def add(a, b):
        key = tuple(sorted((a, b)))
        if key in edges:
            return
        la, lo = nodes[a]
        lb, lob = nodes[b]
        km = round(haversine_km(la, lo, lb, lob) * 1.3 + 0.5, 1)
        mid = ((la + lb) / 2, (lo + lob) / 2)
        d = haversine_km(EPI[0], EPI[1], *mid)
        r = rng.random()
        status = "CERRADA" if r < 0.55 * math.exp(-d / 30) else "RESTRINGIDA" if r < 0.55 * math.exp(-d / 30) + 0.35 * math.exp(-d / 40) else "ABIERTA"
        edges[key] = {"a": key[0], "b": key[1], "km": km, "speed_kmh": rng.choice([50, 60, 70, 80]), "status": status}

    for a in ids:
        near = sorted((haversine_km(*nodes[a], *nodes[b]), b) for b in ids if b != a)[:2]
        for _, b in near:
            add(a, b)
    # unir componentes (ignorando estado) con la arista más corta entre ellas
    def comps():
        adj = {i: set() for i in ids}
        for a, b in edges:
            adj[a].add(b)
            adj[b].add(a)
        seen, out = set(), []
        for s in ids:
            if s in seen:
                continue
            comp, st = {s}, [s]
            while st:
                u = st.pop()
                for v in adj[u] - comp:
                    comp.add(v)
                    st.append(v)
            seen |= comp
            out.append(comp)
        return out

    cs = comps()
    while len(cs) > 1:
        base = cs[0]
        best = min((haversine_km(*nodes[a], *nodes[b]), a, b) for a in base for c in cs[1:] for b in c)
        add(best[1], best[2])
        cs = comps()
    return list(edges.values())


def make_lots(rng, munis, donor_ids):
    total_need = {c: sum(m[f"need_{c.value.lower()}"] for m in munis) for c in Category}
    hubs = list(HUB_WEIGHT)
    weights = [HUB_WEIGHT[h] for h in hubs]
    rows, n = [], 0
    for cat in Category:
        shares = [rng.lognormvariate(0, 0.8) for _ in range(N_LOTS[cat])]
        s = sum(shares)
        target = total_need[cat] * COVERAGE[cat]
        for sh in shares:
            n += 1
            qty = max(1, round(target * sh / s))
            uw, uv = UNIT_W[cat]
            received = EVENT + timedelta(days=rng.randint(0, 2))
            expiry, cold = "", False
            if cat is Category.MEDICO:
                cold = rng.random() < 0.3
                expiry = received + timedelta(days=rng.randint(10, 45) if cold else rng.randint(60, 400))
            elif cat is Category.VIVERES:
                expiry = received + timedelta(days=rng.randint(90, 700))
            elif cat is Category.AGUA:
                expiry = received + timedelta(days=rng.randint(180, 400))
            desc = rng.choice(DESC[cat])
            if "Vacunas" in desc:
                cold = True
                expiry = expiry or received + timedelta(days=30)
            if cat is Category.MEDICO and "Vacunas" not in desc and cold:
                desc = "Vacunas y biológicos (cadena de frío)"
            rows.append({
                "lot_id": f"L-{n:04d}", "donor_id": rng.choice(donor_ids), "category": cat.value, "description": desc,
                "quantity": qty, "unit": CATEGORY_UNITS[cat], "weight_kg": round(qty * uw, 1), "volume_m3": round(qty * uv, 3),
                "hub_id": rng.choices(hubs, weights)[0], "received": received.isoformat(),
                "expiry": expiry.isoformat() if expiry else "", "cold_chain": str(cold).lower(),
                "available": qty, "status": "DISPONIBLE",
            })
    # lotes perecederos que vencen pronto (alertas tempranas)
    for desc, cat, qty in [("Pan y alimentos frescos", Category.VIVERES, 4000), ("Pan y alimentos frescos", Category.VIVERES, 2500),
                           ("Fruta y lácteos", Category.VIVERES, 3000), ("Plaquetas y hemoderivados", Category.MEDICO, 300),
                           ("Insulina y biológicos", Category.MEDICO, 500), ("Alimentos preparados", Category.VIVERES, 5000)]:
        n += 1
        uw, uv = UNIT_W[cat]
        received = EVENT + timedelta(days=2)
        rows.append({
            "lot_id": f"L-{n:04d}", "donor_id": rng.choice(donor_ids), "category": cat.value, "description": desc,
            "quantity": qty, "unit": CATEGORY_UNITS[cat], "weight_kg": round(qty * uw, 1), "volume_m3": round(qty * uv, 3),
            "hub_id": rng.choice(["H-BOG", "H-PEI", "H-MDE", "H-CLO"]), "received": received.isoformat(),
            "expiry": (EVENT + timedelta(days=rng.randint(5, 9))).isoformat(),
            "cold_chain": str(cat is Category.MEDICO).lower(), "available": qty, "status": "DISPONIBLE",
        })
    return rows


def main():
    rng = random.Random(SEED)
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    (data / "event.json").write_text(json.dumps({
        "name": "Sismo sintético del Eje Cafetero (escenario de simulación)", "event_date": EVENT.isoformat(),
        "epicenter_lat": EPI[0], "epicenter_lon": EPI[1], "magnitude": 6.8}, ensure_ascii=False, indent=2), encoding="utf-8")

    donors = [{"donor_id": f"D-{i:03d}", "name": n, "kind": k, "origin": rng.choice(DONOR_ORIGIN)}
              for i, (n, k) in enumerate(DONOR_NAMES, 1)]
    write_csv(data / "donors.csv", ["donor_id", "name", "kind", "origin"], donors)
    write_csv(data / "hubs.csv", ["hub_id", "name", "department", "kind", "lat", "lon", "capacity_m3"],
              [dict(zip(["hub_id", "name", "department", "kind", "lat", "lon", "capacity_m3"], h)) for h in HUBS])
    munis = make_municipalities(rng)
    write_csv(data / "municipalities.csv", list(munis[0].keys()), munis)
    nodes = {h[0]: (h[4], h[5]) for h in HUBS}
    nodes.update({m["muni_id"]: (m["lat"], m["lon"]) for m in munis})
    write_csv(data / "roads.csv", ["a", "b", "km", "speed_kmh", "status"], make_roads(rng, nodes))
    lots = make_lots(rng, munis, [d["donor_id"] for d in donors])
    write_csv(data / "lots.csv", list(lots[0].keys()), lots)
    print(f"Datos generados en {data}: {len(munis)} municipios, {len(HUBS)} centros, {len(lots)} lotes")


if __name__ == "__main__":
    main()
