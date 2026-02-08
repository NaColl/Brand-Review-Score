"""Brand Sentiment Score (BSS) v2 — Command-Line Interface.

Usage:
    python cli.py score --brand "Tesla" --ticker TSLA
    python cli.py score --config config/brands_example.yaml
    python cli.py compare --brands "Tesla,Ford,GM"
    python cli.py score --brand "Gucci" --luxury
    python cli.py export --brand "Nike" --format json --output report.json

Demo mode (uses realistic built-in data, no network required):
    python cli.py demo --brand Nike
    python cli.py demo --brand Chanel
    python cli.py demo --all
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


# ─────────────────────────────────────────────────────────────────────────
# Demo command — works offline with realistic built-in data
# ─────────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--brand", "-b", type=str, default=None, help="Demo brand: Nike, Chanel, Tesla, Gap")
@click.option("--all", "run_all", is_flag=True, default=False, help="Score all 4 demo brands.")
@click.option("--engine", "-e", type=click.Choice(["vader", "textblob", "ensemble"]), default="vader")
@click.option("--output", "-o", type=str, default=None, help="Output file path (JSON).")
def demo(brand: str | None, run_all: bool, engine: str, output: str | None) -> None:
    """Run BSS scoring with built-in demo data (no network required)."""
    from src.demo import generate_demo_data, generate_demo_competitors, get_demo_brand, list_demo_brands

    if not brand and not run_all:
        available = list_demo_brands()
        click.echo(f"Available demo brands: {', '.join(available)}")
        click.echo("Usage: python cli.py demo --brand Nike")
        click.echo("       python cli.py demo --all")
        return

    brand_names = list_demo_brands() if run_all else [brand]
    reporter = ConsoleReporter()
    signal_gen = SignalGenerator()
    exporter = ExportReporter()
    results = []

    # Demo sale/pricing data per brand
    demo_pricing = {
        "Nike": {"sale_pct": 0.25, "discount_pct": 0.30, "resale_ratio": 0.72},
        "Chanel": {"sale_pct": 0.02, "discount_pct": 0.0, "resale_ratio": 0.85},
        "Tesla": {"sale_pct": None, "discount_pct": None, "resale_ratio": 0.68},
        "Gap": {"sale_pct": 0.55, "discount_pct": 0.45, "resale_ratio": 0.15},
    }

    # Demo stock price changes for signal generation
    demo_price_changes = {
        "Nike": 5.2,
        "Chanel": None,
        "Tesla": -3.8,
        "Gap": -12.4,
    }

    for name in brand_names:
        try:
            brand_obj = get_demo_brand(name)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            continue

        demo_data = generate_demo_data(name)
        demo_competitors = generate_demo_competitors(name)
        pricing = demo_pricing.get(name, {})

        calculator = BSSCalculator(sentiment_engine=engine)
        bss = calculator.calculate(
            brand_obj,
            sale_percentage=pricing.get("sale_pct"),
            avg_discount_pct=pricing.get("discount_pct"),
            resale_value_ratio=pricing.get("resale_ratio"),
            demo_data=demo_data,
            demo_competitors=demo_competitors,
        )

        price_change = demo_price_changes.get(name)
        signal = signal_gen.generate(bss, price_change_pct=price_change)

        reporter.report(bss, signal)
        results.append(bss)

        if output and not run_all:
            exporter.to_json(bss, signal, output_path=output)
            click.echo(f"\nJSON report saved to: {output}")

    # Comparison summary for --all
    if run_all and len(results) > 1:
        click.echo("\n" + "=" * 60)
        click.echo("  DEMO COMPARISON — 4 Brand Archetypes")
        click.echo("=" * 60)
        sorted_results = sorted(results, key=lambda r: r.bss, reverse=True)
        for i, r in enumerate(sorted_results, 1):
            lux = " [LUXURY]" if r.is_luxury else ""
            click.echo(f"  {i}. {r.brand_name:12s}  {r.bss:5.1f}/100  ({r.grade():>2s}){lux}")
        click.echo()

        if output:
            exporter.to_csv(results, output)
            click.echo(f"CSV comparison saved to: {output}")


# ─────────────────────────────────────────────────────────────────────────
# Live scoring commands (require network)
# ─────────────────────────────────────────────────────────────────────────

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
    """Calculate the Brand Sentiment Score for one or more brands (live data)."""
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
    """Compare BSS scores across multiple brands (live data)."""
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
