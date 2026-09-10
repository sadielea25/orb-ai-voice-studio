"""
desktop_operator.py
Master Conversational Desktop Operator.
Orchestrates vision, mouse/keyboard actuation, and task execution.
"""

import sys
import os
import argparse
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

from mouse_controller import MouseController
from vision_engine import VisionEngine
from watchdog_loop import WatchdogLoop
from fill_aa02 import fill_aa02_form

console = Console()


class DesktopOperator:
    def __init__(self):
        self.mouse = MouseController()
        self.vision = VisionEngine()
        self.watchdog = WatchdogLoop()

    def run_aa02_workflow(
        self,
        unpaid: str = "1",
        cash: str = "0",
        shares: str = "1",
        share_class: str = "Ordinary",
        value: str = "1",
        date: str = None
    ):
        console.print(Panel.fit("[bold green]Executing Companies House AA02 Workflow[/bold green]"))

        # 1. Capture screen before action
        console.print("[yellow]Capturing screen state...[/yellow]")
        self.vision.capture_screen("aa02_start.png")

        # 2. Fill form via DOM / Playwright / Actuation
        console.print("[cyan]Populating AA02 form fields...[/cyan]")
        fill_aa02_form(
            unpaid_capital=unpaid,
            cash_in_bank=cash,
            num_shares=shares,
            share_class=share_class,
            share_value=value,
            approval_date=date or datetime.now().strftime("%d/%m/%Y"),
            click_validate=False
        )

        # 3. Capture verification frame
        console.print("[green]Capturing verification screenshot...[/green]")
        verification_image = self.vision.capture_screen("aa02_completed.png")
        console.print(f"[bold green]✔ Done! Verification frame saved to: {verification_image}[/bold green]")


def main():
    parser = argparse.ArgumentParser(description="Desktop Operator CLI")
    parser.add_argument("command", choices=["fill-aa02", "inspect", "screenshot"], default="fill-aa02", nargs="?")
    parser.add_argument("--unpaid", default="1")
    parser.add_argument("--cash", default="0")
    parser.add_argument("--shares", default="1")
    parser.add_argument("--class", dest="share_class", default="Ordinary")
    parser.add_argument("--value", default="1")
    parser.add_argument("--date", default=None)

    args = parser.parse_args()

    operator = DesktopOperator()

    if args.command == "fill-aa02":
        operator.run_aa02_workflow(
            unpaid=args.unpaid,
            cash=args.cash,
            shares=args.shares,
            share_class=args.share_class,
            value=args.value,
            date=args.date
        )
    elif args.command == "screenshot":
        path = operator.vision.capture_screen("desktop_snapshot.png")
        print(f"Screenshot saved to: {path}")


if __name__ == "__main__":
    main()
