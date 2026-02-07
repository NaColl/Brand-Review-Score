"""Export BSS results to JSON and CSV."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from src.models.score import BrandSentimentScore, PredictiveSignal

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
            "brand", "timestamp", "bss", "grade", "confidence",
            "review_quality", "social_sentiment", "momentum",
            "brand_health", "competitive_position",
            "data_sources", "total_data_points",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for bss in results:
                writer.writerow({
                    "brand": bss.brand_name,
                    "timestamp": bss.timestamp.isoformat(),
                    "bss": round(bss.bss, 2),
                    "grade": bss.grade(),
                    "confidence": round(bss.confidence, 2),
                    "review_quality": round(bss.review_quality.value, 2) if bss.review_quality else "",
                    "social_sentiment": round(bss.social_sentiment.value, 2) if bss.social_sentiment else "",
                    "momentum": round(bss.momentum.value, 2) if bss.momentum else "",
                    "brand_health": round(bss.brand_health.value, 2) if bss.brand_health else "",
                    "competitive_position": round(bss.competitive_position.value, 2) if bss.competitive_position else "",
                    "data_sources": ",".join(bss.data_sources_used),
                    "total_data_points": bss.total_data_points,
                })

        logger.info("CSV report written to %s (%d brands)", path, len(results))
