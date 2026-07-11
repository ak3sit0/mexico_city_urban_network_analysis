"""
Phase 5, Paso 0: Vehicle capacity assumptions.

Documents the assumed passenger capacity per vehicle for each agency.
This is a required input for Paso 1 (per-node capacity C_i) and Paso 2
(load distribution L_i) of the cascading failure simulation (Motter-Lai model).

Constraints:
- One capacity value per agency (no per-route/line variation documented here).
- Sourced from official fleet specs, GTFS metadata, or engineering estimates
  for agencies without public data.
- Confidence levels vary (see CAPACITY_NOTES) — marked explicitly to avoid
  treating all values equally in sensitivity analysis.

Caveat: This is a documented assumption, not real boarding data. Absence of
detailed fleet composition (e.g., METRO has both 6-car and 9-car trains) is
reflected in confidence levels.

Agencies (10 total):
  CBB, CC, INTERURBANO, MB, METRO, PUMABUS, RTP, SUB, TL, TROLE
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

CAPACITY_PER_VEHICLE: dict[str, int] = {
    "CBB": 10,              # Cablebús: cabinas de 10 pax
    "CC": 80,               # Corredores Concesionados: autobús rápido estándar
    "INTERURBANO": 719,     # Tren México-Toluca "El Insurgente": 5 vagones CAF Civity (326 asientos + pie)
    "MB": 160,              # Metrobús: autobús articulado estándar
    "METRO": 1300,          # Metro: representativo entre líneas 6 y 9 vagones (6: ~1,130; 9: ~1,500)
    "PUMABUS": 40,          # PUMABÚS: shuttle UNAM, estimación (sin dato oficial de flota)
    "RTP": 80,              # Red de Transporte de Pasajeros: autobús rápido
    "SUB": 1130,            # Tren Suburbano: línea original Buenavista-Cuautitlán (4 vagones, oficial)
    "TL": 400,              # Tren Ligero Xochimilco: flota mixta en transición (viejas 374, CRRC 292, nuevas 750)
    "TROLE": 90,            # Trolebús: estándar de trolebús urbano
}

CAPACITY_NOTES: dict[str, str] = {
    "CBB": "Cablelift cabins, 10 pax each. Verified from operational specs.",
    "CC": "Standard rapid bus (autobús articulado). Typical urban rapid transit capacity.",
    "INTERURBANO": "Official: Tren México-Toluca 'El Insurgente' (CAF Civity, 5-car), 326 seats + standing room. High confidence.",
    "MB": "Standard articulated bus (BRT). High confidence.",
    "METRO": "Mix across lines: 6-car trains ~1,130 pax, 9-car trains ~1,500 pax. Value 1,300 is representative of fleet average. Medium confidence (simplified single value).",
    "PUMABUS": "UNAM shuttle bus, estimated ~40 pax. No official fleet data found — weakest assumption in table. Low confidence.",
    "RTP": "Rapid transit bus. Same as CC, 80 pax.",
    "SUB": "Tren Suburbano official capacity for Buenavista-Cuautitlán line (4-car trains, 1,130 pax). AIFA extension uses different fleet but GTFS groups under SUB. High confidence for original line.",
    "TL": "Tren Ligero Xochimilco: mixed fleet in transition (old units 374 pax, CRRC intermediate 292 pax, new 'El Ajolote' 750 pax with 17 units entering service 2026). Value 400 is representative of current mixed fleet. Will become obsolete as new fleet dominates. Medium confidence.",
    "TROLE": "Standard trolleybus (trolebús urbano). Typical urban rapid transit capacity.",
}

METHODOLOGY_CAVEATS: list[str] = [
    "This is a documented assumption, not real passenger boarding data. Absence of origin-destination (OD) demand matrix means we use capacity as a proxy for load distribution.",
    "One capacity value per agency — no per-route, per-line, or time-of-day variation. METRO's mix of 6-car and 9-car trains, TL's fleet transition, and SUB's two distinct train types (Buenavista vs. AIFA) are simplified to single values.",
    "PUMABUS is the weakest assumption (estimated ~40 pax from typical university shuttle specs; no official UNAM fleet composition found). Use caution in sensitivity analysis.",
    "TL's value will become invalid once the 'El Ajolote' fleet (750 pax) dominates operations (expected 2026+). This table should be revisited before interpreting results from that date onward.",
    "These values feed directly into per-node capacity C_i (Paso 1) and load distribution L_i (Paso 2). Errors or outdated assumptions here propagate through cascading failure results (Pasos 3-6).",
]


def export_csv(out_path: str | Path) -> None:
    """Export capacity assumptions to CSV for cross-language use (Python/Julia)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["agency_id", "capacity_per_vehicle", "note"])
        writer.writeheader()
        for agency_id in sorted(CAPACITY_PER_VEHICLE.keys()):
            writer.writerow({
                "agency_id": agency_id,
                "capacity_per_vehicle": CAPACITY_PER_VEHICLE[agency_id],
                "note": CAPACITY_NOTES[agency_id],
            })


def main() -> None:
    """Print capacity assumptions to console and export to CSV."""
    print("=" * 80)
    print("FASE 5, PASO 0: Supuestos de capacidad por vehículo")
    print("=" * 80)
    print()

    print("Tabla de capacidades (10 agencias):")
    print("-" * 80)
    print(f"{'Agencia':<15} {'Capacidad (pax)':<18} {'Nota':<47}")
    print("-" * 80)
    for agency_id in sorted(CAPACITY_PER_VEHICLE.keys()):
        cap = CAPACITY_PER_VEHICLE[agency_id]
        note = CAPACITY_NOTES[agency_id][:43] + "..." if len(CAPACITY_NOTES[agency_id]) > 43 else CAPACITY_NOTES[agency_id]
        print(f"{agency_id:<15} {cap:<18} {note:<47}")
    print()

    print("Caveats metodológicos:")
    print("-" * 80)
    for i, caveat in enumerate(METHODOLOGY_CAVEATS, 1):
        print(f"{i}. {caveat}")
    print()

    out_csv = Path(__file__).resolve().parent.parent / "data" / "processed" / "capacity_assumptions.csv"
    export_csv(out_csv)
    print(f"✓ Exportado: {out_csv}")
    print(f"✓ {len(CAPACITY_PER_VEHICLE)} agencias documentadas (verificar contra nodes.parquet)")
    print()


if __name__ == "__main__":
    main()
