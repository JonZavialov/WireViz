# -*- coding: utf-8 -*-
"""Utility to convert database wire harness records into a WireViz YAML string.

This helper is intended for environments where the harness information is stored
in a database. The querying itself is outside the scope of this module; the
expected input is an iterable of dictionaries where each dictionary represents
one row returned from the database.

Only rows with ``classcode_code`` equal to ``"WIRE, INSULATED"`` are
interpreted as wires. The ``bomitem_notes`` field is assumed to contain the two
connector identifiers separated by ``--``. Each wire results in two simple
connectors and one cable connecting them.
"""

from typing import Dict, Iterable, List

import yaml


def _parse_wire_spec(spec: str) -> Dict[str, str]:
    """Parse the encoded wire specification string.

    The specification uses the format ``A-B-C-D-E-F-G`` where each part is
    described in the project documentation. Only the color and gauge are used
    in the generated YAML, but all fields are returned for completeness.
    """
    parts = [p.strip() for p in spec.split("-")]
    if len(parts) < 7:
        raise ValueError(f"Unexpected wire spec: {spec}")
    return {
        "gauge": parts[0],
        "voltage": parts[1],
        "insulation": parts[2],
        "color": parts[3],
        "strand_gauge": parts[4],
        "strand_count": parts[5],
        "conductor_count": parts[6],
    }


def generate_yaml(records: Iterable[Dict[str, str]]) -> str:
    """Convert database records to WireViz YAML.

    Parameters
    ----------
    records:
        Iterable containing dictionaries for each BOM row. Every row must
        provide at least the keys ``classcode_code``, ``bomitem_notes``,
        ``bomitem_ref``, ``bomitem_qtyper``, ``uom_name`` and ``item_descrip2``.

    Returns
    -------
    str
        YAML string ready to be consumed by :func:`wireviz.parse`.
    """

    connectors: Dict[str, Dict] = {}
    cables: Dict[str, Dict] = {}
    connections: List[List[Dict[str, int]]] = []

    for idx, row in enumerate(records, start=1):
        if row.get("classcode_code") != "WIRE, INSULATED":
            continue
        notes = row.get("bomitem_notes", "")
        try:
            left, right = [n for n in notes.split("--") if n]
        except ValueError:
            # notes may not contain two sides; skip this row
            continue
        wire_name = row.get("bomitem_ref") or f"W{idx}"
        spec = _parse_wire_spec(row.get("item_descrip2", ""))

        for conn in (left, right):
            connectors.setdefault(conn, {"style": "simple"})

        cables[wire_name] = {
            "wirecount": 1,
            "colors": [spec["color"]],
            "gauge": spec["gauge"],
            "length": f"{row.get('bomitem_qtyper')} {row.get('uom_name')}",
        }

        connections.append([{left: 1}, {wire_name: 1}, {right: 1}])

    data = {
        "connectors": connectors,
        "cables": cables,
        "connections": connections,
    }
    return yaml.dump(data, sort_keys=False)


__all__ = ["generate_yaml"]
