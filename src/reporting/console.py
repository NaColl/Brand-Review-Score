"""Rich console output for BSS v2 reports."""

from __future__ import annotations

from config.settings import DIMENSION_WEIGHTS, LUXURY_DIMENSION_WEIGHTS
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.models.score import (
    ALL_DIMENSION_ATTRS,
    BrandSentimentScore,
    PredictiveSignal,
)


class ConsoleReporter:
    """Renders BSS results as formatted console output using Rich."""

    def __init__(self) -> None:
        self.console = Console()

    def report(
        self,
        bss: BrandSentimentScore,
        signal: PredictiveSignal | None = None,
    ) -> None:
        """Print a full BSS report to the console."""
        self.console.print()
        self._print_header(bss)
        self._print_dimensions(bss)
        if bss.hype_health:
            self._print_hype_health(bss)
        if bss.luxury_index:
            self._print_luxury_index(bss)
        self._print_data_quality(bss)
        if signal:
            self._print_signal(signal)
        self.console.print()

    def _print_header(self, bss: BrandSentimentScore) -> None:
        grade = bss.grade()
        grade_color = _grade_color(grade)

        score_text = Text()
        score_text.append("  BSS: ", style="bold")
        score_text.append(f"{bss.bss:.1f}", style=f"bold {grade_color}")
        score_text.append(" / 100  ", style="bold")
        score_text.append(f"[{grade}]", style=f"bold {grade_color}")
        if bss.is_luxury:
            score_text.append("  ", style="bold")
            score_text.append("LUXURY", style="bold magenta")

        panel = Panel(
            score_text,
            title=f"[bold]{bss.brand_name}[/bold] — Brand Sentiment Score",
            subtitle=bss.timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            border_style=grade_color,
            padding=(1, 2),
        )
        self.console.print(panel)

    def _print_dimensions(self, bss: BrandSentimentScore) -> None:
        weights = LUXURY_DIMENSION_WEIGHTS if bss.is_luxury else DIMENSION_WEIGHTS

        table = Table(
            title="8 Scoring Dimensions",
            show_header=True,
            header_style="bold cyan",
            padding=(0, 2),
        )
        table.add_column("#", width=3)
        table.add_column("Dimension", style="bold", width=24)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Weight", justify="right", width=8)
        table.add_column("Bar", width=22)
        table.add_column("Details", width=45)

        for i, dim_attr in enumerate(ALL_DIMENSION_ATTRS, 1):
            dim = getattr(bss, dim_attr, None)
            if dim is None:
                continue
            weight = weights.get(dim_attr, 0)
            bar = _score_bar(dim.value)
            color = _score_color(dim.value)
            table.add_row(
                str(i),
                dim.name,
                f"[{color}]{dim.value:.1f}[/{color}]",
                f"{weight:.0%}",
                bar,
                dim.explanation[:45] if dim.explanation else "",
            )

        self.console.print(table)

    def _print_hype_health(self, bss: BrandSentimentScore) -> None:
        hhi = bss.hype_health
        if not hhi:
            return

        quadrant_labels = {
            "strong_brand": ("green", "STRONG BRAND (ideal)"),
            "overhyped": ("red", "OVERHYPED (bubble risk)"),
            "hidden_gem": ("cyan", "HIDDEN GEM (undervalued)"),
            "declining": ("rgb(255,165,0)", "DECLINING"),
        }
        color, label = quadrant_labels.get(hhi.quadrant, ("yellow", hhi.quadrant))

        text = Text()
        text.append("  Hype:   ", style="bold")
        text.append(f"{hhi.hype_score:.1f}", style="bold magenta")
        text.append(" / 100\n")
        text.append("  Health: ", style="bold")
        text.append(f"{hhi.health_score:.1f}", style="bold blue")
        text.append(" / 100\n\n")
        text.append("  Quadrant: ", style="bold")
        text.append(label, style=f"bold {color}")
        divergence = hhi.divergence
        if abs(divergence) > 10:
            text.append(f"\n  Divergence: {divergence:+.1f}", style="dim")

        panel = Panel(
            text,
            title="Hype vs Health Index",
            border_style=color,
            padding=(0, 2),
        )
        self.console.print(panel)

    def _print_luxury_index(self, bss: BrandSentimentScore) -> None:
        lux = bss.luxury_index
        if not lux:
            return

        table = Table(show_header=False, padding=(0, 2), box=None)
        table.add_column("Metric", style="bold magenta")
        table.add_column("Value")

        table.add_row("Luxury Index", f"{lux.composite:.1f}/100")
        if lux.resale_premium_ratio > 0:
            rpr = lux.resale_premium_ratio
            rpr_color = "green" if rpr >= 1.0 else "yellow" if rpr >= 0.7 else "red"
            table.add_row("Resale Premium", f"[{rpr_color}]{rpr:.0%}[/{rpr_color}]")
        table.add_row("Exclusivity", f"{lux.exclusivity_score:.0f}/100")
        table.add_row("Aspirational", f"{lux.aspirational_score:.0f}/100")
        table.add_row("Heritage", f"{lux.heritage_score:.0f}/100")

        panel = Panel(table, title="Luxury Brand Index", border_style="magenta")
        self.console.print(panel)

    def _print_data_quality(self, bss: BrandSentimentScore) -> None:
        conf_pct = bss.confidence * 100
        conf_color = "green" if conf_pct >= 70 else "yellow" if conf_pct >= 40 else "red"

        table = Table(show_header=False, padding=(0, 2), box=None)
        table.add_column("Label", style="dim")
        table.add_column("Value")

        table.add_row(
            "Data Sources",
            ", ".join(bss.data_sources_used) if bss.data_sources_used else "none",
        )
        table.add_row("Total Data Points", str(bss.total_data_points))
        table.add_row(
            "Confidence",
            f"[{conf_color}]{conf_pct:.0f}%[/{conf_color}]",
        )

        panel = Panel(table, title="Data Quality", border_style="dim")
        self.console.print(panel)

    def _print_signal(self, signal: PredictiveSignal) -> None:
        signal_styles = {
            "strong_bullish": ("bold green", "STRONG BULLISH"),
            "moderate_bullish": ("green", "MODERATE BULLISH"),
            "neutral": ("yellow", "NEUTRAL"),
            "moderate_bearish": ("red", "MODERATE BEARISH"),
            "strong_bearish": ("bold red", "STRONG BEARISH"),
        }

        style, label = signal_styles.get(signal.signal, ("yellow", signal.signal))

        text = Text()
        text.append("  Signal: ", style="bold")
        text.append(label, style=style)
        text.append(f"  (delta: {signal.bss_delta:+.1f} pts)\n")

        if signal.divergence_signal and signal.divergence_signal != "aligned":
            div_style = "green" if signal.divergence_signal == "undervalued" else "red"
            text.append("  Divergence: ", style="bold")
            text.append(signal.divergence_signal.upper(), style=div_style)
            if signal.price_change_pct is not None:
                text.append(f"  (price: {signal.price_change_pct:+.1f}%)")
            text.append("\n")

        if signal.hhi_quadrant:
            text.append(f"\n  HHI Quadrant: {signal.hhi_quadrant}", style="dim")

        text.append(f"\n  {signal.explanation}", style="dim")

        panel = Panel(
            text,
            title="Predictive Signal",
            border_style=style.split()[-1] if " " in style else style,
            padding=(0, 2),
        )
        self.console.print(panel)


def _score_bar(value: float, width: int = 20) -> str:
    filled = int((value / 100) * width)
    empty = width - filled
    color = _score_color(value)
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"


def _score_color(value: float) -> str:
    if value >= 70:
        return "green"
    elif value >= 50:
        return "yellow"
    elif value >= 30:
        return "rgb(255,165,0)"
    else:
        return "red"


def _grade_color(grade: str) -> str:
    if grade.startswith("A"):
        return "green"
    elif grade.startswith("B"):
        return "cyan"
    elif grade == "C":
        return "yellow"
    elif grade == "D":
        return "rgb(255,165,0)"
    else:
        return "red"
