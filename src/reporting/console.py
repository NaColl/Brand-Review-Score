"""Rich console output for BSS reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.models.score import BrandSentimentScore, PredictiveSignal


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
        self._print_data_quality(bss)
        if signal:
            self._print_signal(signal)
        self.console.print()

    def _print_header(self, bss: BrandSentimentScore) -> None:
        grade = bss.grade()
        grade_color = _grade_color(grade)

        score_text = Text()
        score_text.append(f"  BSS: ", style="bold")
        score_text.append(f"{bss.bss:.1f}", style=f"bold {grade_color}")
        score_text.append(f" / 100  ", style="bold")
        score_text.append(f"[{grade}]", style=f"bold {grade_color}")

        panel = Panel(
            score_text,
            title=f"[bold]{bss.brand_name}[/bold] — Brand Sentiment Score",
            subtitle=bss.timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            border_style=grade_color,
            padding=(1, 2),
        )
        self.console.print(panel)

    def _print_dimensions(self, bss: BrandSentimentScore) -> None:
        table = Table(
            title="Scoring Dimensions",
            show_header=True,
            header_style="bold cyan",
            padding=(0, 2),
        )
        table.add_column("Dimension", style="bold", width=30)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Weight", justify="right", width=8)
        table.add_column("Bar", width=22)
        table.add_column("Details", width=50)

        dimensions = [
            (bss.review_quality, 0.25),
            (bss.social_sentiment, 0.20),
            (bss.momentum, 0.25),
            (bss.brand_health, 0.15),
            (bss.competitive_position, 0.15),
        ]

        for dim, weight in dimensions:
            if dim is None:
                continue
            bar = _score_bar(dim.value)
            color = _score_color(dim.value)
            table.add_row(
                dim.name,
                f"[{color}]{dim.value:.1f}[/{color}]",
                f"{weight:.0%}",
                bar,
                dim.explanation[:50] if dim.explanation else "",
            )

        self.console.print(table)

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
            text.append(f"  Divergence: ", style="bold")
            text.append(signal.divergence_signal.upper(), style=div_style)
            if signal.price_change_pct is not None:
                text.append(f"  (price: {signal.price_change_pct:+.1f}%)")
            text.append("\n")

        text.append(f"\n  {signal.explanation}", style="dim")

        panel = Panel(
            text,
            title="Predictive Signal",
            border_style=style.split()[-1] if " " in style else style,
            padding=(0, 2),
        )
        self.console.print(panel)


def _score_bar(value: float, width: int = 20) -> str:
    """Create a colored bar visualization of a 0–100 score."""
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
