"""Export BSS v2 results to JSON and CSV."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from src.models.score import ALL_DIMENSION_ATTRS, BrandSentimentScore, PredictiveSignal

logger = logging.getLogger(__name__)


class ExportReporter:
    """Exports BSS results to JSON and CSV files."""

    def to_json(
        self,
        bss: BrandSentimentScore,
        signal: PredictiveSignal | None = None,
        output_path: str | Path | None = None,
    ) -> str:
        """Export to JSON. Returns the JSON string and optionally writes to file."""
        data = bss.to_dict()
        if signal:
            data["predictive_signal"] = signal.to_dict()

        json_str = json.dumps(data, indent=2, default=str)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str)
            logger.info("JSON report written to %s", path)

        return json_str

    def to_csv(
        self,
        results: list[BrandSentimentScore],
        output_path: str | Path,
    ) -> None:
        """Export multiple BSS results to CSV (one row per brand)."""
        if not results:
            return

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "brand", "timestamp", "bss", "grade", "is_luxury", "confidence",
        ] + ALL_DIMENSION_ATTRS + [
            "hhi_hype", "hhi_health", "hhi_quadrant",
            "luxury_index",
            "data_sources", "total_data_points",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for bss in results:
                row = {
                    "brand": bss.brand_name,
                    "timestamp": bss.timestamp.isoformat(),
                    "bss": round(bss.bss, 2),
                    "grade": bss.grade(),
                    "is_luxury": bss.is_luxury,
                    "confidence": round(bss.confidence, 2),
                    "data_sources": ",".join(bss.data_sources_used),
                    "total_data_points": bss.total_data_points,
                }

                # 8 dimensions
                for dim_attr in ALL_DIMENSION_ATTRS:
                    dim = getattr(bss, dim_attr)
                    row[dim_attr] = round(dim.value, 2) if dim else ""

                # HHI
                if bss.hype_health:
                    row["hhi_hype"] = round(bss.hype_health.hype_score, 2)
                    row["hhi_health"] = round(bss.hype_health.health_score, 2)
                    row["hhi_quadrant"] = bss.hype_health.quadrant
                else:
                    row["hhi_hype"] = ""
                    row["hhi_health"] = ""
                    row["hhi_quadrant"] = ""

                # Luxury index
                row["luxury_index"] = (
                    round(bss.luxury_index.composite, 2) if bss.luxury_index else ""
                )

                writer.writerow(row)

        logger.info("CSV report written to %s (%d brands)", path, len(results))
