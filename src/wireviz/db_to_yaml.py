# -*- coding: utf-8 -*-
"""Utility to convert database wire harness records into a WireViz YAML string.

This helper is intended for environments where the harness information is stored
in a database. The querying itself is outside the scope of this module; the
expected input is an iterable of dictionaries where each dictionary represents
one row returned from the database.

Only rows with ``classcode_code`` equal to ``"WIRE, INSULATED"`` are
interpreted as wires. The ``bomitem_notes`` field is assumed to contain the two
connector identifiers separated by ``--``. Designators are sanitized so that
each uses at most one ``.`` character because that is the separator understood
by WireViz. Each wire results in two simple connectors and one cable connecting
them.
"""

from typing import Dict, Iterable, List

import json
import re


def _sanitize_designator(name: str) -> str:
    """Return a designator usable by WireViz.

    The WireViz parser is fairly strict about connector names. They should not
    contain spaces or punctuation other than ``.`` and ``-``.  Additionally the
    parser only recognises one ``.`` separator.  Any additional separators are
    therefore replaced with ``-`` and all other invalid characters are turned
    into underscores.
    """

    if not name:
        return ""

    name = name.strip()

    if name.count(".") > 1:
        head, tail = name.split(".", 1)
        tail = tail.replace(".", "-")
        name = f"{head}.{tail}"

    name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return name


def _base_designator(designator: str) -> str:
    """Return the connector portion of a designator.

    WireViz expects connectors to be defined without the pin suffix.
    For example, ``X1.2`` references pin ``2`` on connector ``X1``.
    This helper extracts the ``X1`` part from ``X1.2``.  If no
    separator is present the input is returned unchanged.
    """

    return designator.split(".", 1)[0]


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
        sides = [n.strip() for n in notes.split("--") if n.strip()]
        if len(sides) != 2:
            # notes may not contain two sides; skip this row
            continue
        left_raw, right_raw = sides
        left_san = _sanitize_designator(left_raw)
        right_san = _sanitize_designator(right_raw)

        # Extract connector names and pin numbers
        left_conn, left_pin = left_san.split(".", 1) if "." in left_san else (left_san, "")
        right_conn, right_pin = right_san.split(".", 1) if "." in right_san else (right_san, "")

        # prefix numeric references to avoid clashes with connector pins
        ref = (row.get("bomitem_ref") or f"W{idx}").strip()
        if ref and ref[0].isdigit() and not ref.startswith("W"):
            ref = f"W{ref}"
        wire_name = _sanitize_designator(ref)

        spec = _parse_wire_spec(row.get("item_descrip2", ""))

        for conn in (left_conn, right_conn):
            if conn:
                connectors.setdefault(conn, {"style": "simple"})

        cables[wire_name] = {
            "wirecount": 1,
            "colors": [spec["color"]],
            "gauge": spec["gauge"],
            "length": f"{row.get('bomitem_qtyper')} {row.get('uom_name')}",
        }

        connections.append([
            {left_conn: left_pin or 1},
            {wire_name: 1},
            {right_conn: right_pin or 1},
        ])

    data = {
        "connectors": connectors,
        "cables": cables,
        "connections": connections,
    }

    # ``json.dumps`` produces valid YAML since JSON is a subset of YAML.
    return json.dumps(data, indent=2)


__all__ = ["generate_yaml"]
