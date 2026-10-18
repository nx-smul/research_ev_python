"""Field validation template generation."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.optimization.extensions._io import write_csv


def write_field_template(path, demand_gdf, candidates, solution):
    """Generate field visit template for selected stations."""
    selected = set(np.flatnonzero(solution.x).tolist())
    rows = []
    for index in sorted(selected):
        candidate = candidates[index]
        geometry = candidate.get("geometry")
        point = geometry if hasattr(geometry, "x") else None
        rows.append({
            "candidate_id": str(candidate.get("candidate_id", index)),
            "site_name": candidate.get("site_name", ""),
            "longitude": point.x if point is not None else candidate.get("lon", ""),
            "latitude": point.y if point is not None else candidate.get("lat", ""),
            "visit_date": "",
            "observer": "",
            "public_access_confirmed": "",
            "parking_bays_observed": "",
            "landowner_permission_status": "",
            "utility_connection_contact": "",
            "transformer_rating_mva_observed": "",
            "existing_chargers_observed": "",
            "peak_queue_observed": "",
            "photos_or_evidence_reference": "",
            "field_notes": "",
            "record_status": "not_visited",
        })
    columns = [
        "candidate_id", "site_name", "longitude", "latitude", "visit_date", "observer",
        "public_access_confirmed", "parking_bays_observed", "landowner_permission_status",
        "utility_connection_contact", "transformer_rating_mva_observed",
        "existing_chargers_observed", "peak_queue_observed", "photos_or_evidence_reference",
        "field_notes", "record_status",
    ]
    return write_csv(pd.DataFrame(rows, columns=columns), path)
