"""Brand Sentiment Score (BSS) v2 — Command-Line Interface.

Usage:
    python cli.py score --brand "Tesla" --ticker TSLA
    python cli.py score --config config/brands_example.yaml
    python cli.py compare --brands "Tesla,Ford,GM"
    python cli.py score --brand "Gucci" --luxury
    python cli.py export --brand "Nike" --format json --output report.json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
import yaml

from config.settings import DEFAULT_CONFIG
from src.analysis.sentiment import SentimentAnalyzer
from src.collectors.financial import FinancialCollector
from src.models.brand import Brand
from src.prediction.signals import SignalGenerator
from src.reporting.console import ConsoleReporter
from src.reporting.export import ExportReporter
from src.scoring.composite import BSSCalculator


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _load_brands_from_yaml(path: str) -> list[Brand]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return [Brand.from_dict(b) for b in data.get("brands", [])]


def _make_brand(name: str, ticker: str | None = None, wiki: str | None = None) -> Brand:
    return Brand(
        name=name,
        search_terms=[name],
        ticker=ticker,
        wikipedia_article=wiki or name.replace(" ", "_"),
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
def main(verbose: bool) -> None:
    """Brand Sentiment Score (BSS) v2 — predict brand popularity from free public data."""
    _setup_logging(verbose)


@main.command()
@click.option("--brand", "-b", type=str, help="Brand name to score.")
@click.option("--ticker", "-t", type=str, default=None, help="Stock ticker symbol.")
@click.option("--wiki", "-w", type=str, default=None, help="Wikipedia article title.")
@click.option("--config", "-c", type=click.Path(exists=True), default=None, help="YAML config file.")
@click.option("--engine", "-e", type=click.Choice(["vader", "textblob", "ensemble"]), default="vader")
@click.option("--luxury", is_flag=True, default=False, help="Force luxury brand scoring profile.")
@click.option("--sale-pct", type=float, default=None, help="Percentage of products on sale (0.0-1.0).")
@click.option("--discount-pct", type=float, default=None, help="Average discount percentage (0.0-1.0).")
@click.option("--resale-ratio", type=float, default=None, help="Resale/retail price ratio.")
@click.option("--output", "-o", type=str, default=None, help="Output file path (JSON).")
def score(
    brand: str | None,
    ticker: str | None,
    wiki: str | None,
    config: str | None,
    engine: str,
    luxury: bool,
    sale_pct: float | None,
    discount_pct: float | None,
    resale_ratio: float | None,
    output: str | None,
) -> None:
    """Calculate the Brand Sentiment Score for one or more brands."""
    brands: list[Brand] = []

    if config:
        brands = _load_brands_from_yaml(config)
    elif brand:
        brands = [_make_brand(brand, ticker, wiki)]
    else:
        click.echo("Error: provide --brand or --config", err=True)
        sys.exit(1)

    calculator = BSSCalculator(
        sentiment_engine=engine,
        force_luxury=True if luxury else None,
    )
    reporter = ConsoleReporter()
    signal_gen = SignalGenerator()
    financial = FinancialCollector()
    exporter = ExportReporter()

    for b in brands:
        bss = calculator.calculate(
            b,
            sale_percentage=sale_pct,
            avg_discount_pct=discount_pct,
            resale_value_ratio=resale_ratio,
        )

        # Generate predictive signal
        price_change = financial.get_price_change(b, days=30) if b.ticker else None
        signal = signal_gen.generate(bss, price_change_pct=price_change)

        reporter.report(bss, signal)

        if output:
            exporter.to_json(bss, signal, output_path=output)
            click.echo(f"\nJSON report saved to: {output}")


@main.command()
@click.option("--brands", "-b", type=str, required=True, help="Comma-separated brand names.")
@click.option("--engine", "-e", type=click.Choice(["vader", "textblob", "ensemble"]), default="vader")
@click.option("--luxury", is_flag=True, default=False, help="Force luxury brand scoring profile.")
@click.option("--output", "-o", type=str, default=None, help="Output CSV path.")
def compare(brands: str, engine: str, luxury: bool, output: str | None) -> None:
    """Compare BSS scores across multiple brands."""
    brand_names = [b.strip() for b in brands.split(",")]
    brand_objects = [_make_brand(name) for name in brand_names]

    calculator = BSSCalculator(
        sentiment_engine=engine,
        force_luxury=True if luxury else None,
    )
    reporter = ConsoleReporter()
    exporter = ExportReporter()

    results = []
    for b in brand_objects:
        bss = calculator.calculate(b)
        reporter.report(bss)
        results.append(bss)

    if output:
        exporter.to_csv(results, output)
        click.echo(f"\nCSV report saved to: {output}")

    # Print comparison summary
    if len(results) > 1:
        click.echo("\n--- Comparison Summary ---")
        sorted_results = sorted(results, key=lambda r: r.bss, reverse=True)
        for i, r in enumerate(sorted_results, 1):
            lux = " [LUXURY]" if r.is_luxury else ""
            click.echo(f"  {i}. {r.brand_name}: {r.bss:.1f}/100 ({r.grade()}){lux}")


@main.command()
@click.option("--brand", "-b", type=str, required=True, help="Brand name.")
@click.option("--ticker", "-t", type=str, default=None, help="Stock ticker.")
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "csv"]), default="json")
@click.option("--output", "-o", type=str, required=True, help="Output file path.")
@click.option("--engine", "-e", type=click.Choice(["vader", "textblob", "ensemble"]), default="vader")
@click.option("--luxury", is_flag=True, default=False, help="Force luxury brand scoring profile.")
def export(brand: str, ticker: str | None, fmt: str, output: str, engine: str, luxury: bool) -> None:
    """Export BSS results to a file."""
    b = _make_brand(brand, ticker)
    calculator = BSSCalculator(
        sentiment_engine=engine,
        force_luxury=True if luxury else None,
    )
    bss = calculator.calculate(b)

    exporter = ExportReporter()
    if fmt == "json":
        financial = FinancialCollector()
        price_change = financial.get_price_change(b, days=30) if b.ticker else None
        signal = SignalGenerator().generate(bss, price_change_pct=price_change)
        exporter.to_json(bss, signal, output_path=output)
    else:
        exporter.to_csv([bss], output)

    click.echo(f"Report exported to: {output}")


if __name__ == "__main__":
    main()
