"""
agent.py
Interactive Local Browser Automation Agent CLI.
Attaches to your active browser session and lets you inspect and fill web forms.
"""

import sys
import os
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

from browser_connector import BrowserConnector
from fill_aa02 import fill_aa02_form

console = Console()


def list_tabs():
    connector = BrowserConnector()
    try:
        connector.connect()
        pages = connector.get_pages()
        table = Table(title="Open Browser Tabs")
        table.add_column("#", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("URL", style="white")

        for idx, page in enumerate(pages):
            table.add_row(str(idx + 1), page.title() or "(Untitled)", page.url)
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        connector.close()


def inspect_page():
    connector = BrowserConnector()
    try:
        connector.connect()
        page = connector.get_active_or_first_page()
        console.print(f"[bold green]Active Page:[/bold green] {page.title()} ({page.url})\n")

        elements = page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input, select, textarea, button'));
            return inputs.map((el, i) => {
                let label = '';
                if (el.id) {
                    const l = document.querySelector(`label[for="${el.id}"]`);
                    if (l) label = l.textContent.trim();
                }
                if (!label && el.parentElement) {
                    label = el.parentElement.textContent.replace(/\\s+/g, ' ').trim().slice(0, 50);
                }
                return {
                    index: i + 1,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    value: el.value || '',
                    text: (el.textContent || '').trim().slice(0, 30),
                    label: label
                };
            });
        }""")

        table = Table(title="Form Elements Detected on Page")
        table.add_column("#", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Name / ID", style="yellow")
        table.add_column("Current Value / Text", style="white")
        table.add_column("Nearby Label / Context", style="green")

        for el in elements:
            if el["type"] not in ["hidden"]:
                name_id = el["name"] or el["id"] or "-"
                val_text = el["value"] or el["text"] or "-"
                table.add_row(str(el["index"]), f"{el['tag']}:{el['type']}", name_id, val_text[:30], el["label"][:40])

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        connector.close()


def take_screenshot(filename: str = "screenshot.png"):
    connector = BrowserConnector()
    try:
        connector.connect()
        page = connector.get_active_or_first_page()
        page.screenshot(path=filename)
        console.print(f"[bold green]✔ Screenshot saved to {filename}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        connector.close()


def main():
    console.print(Panel.fit(
        "[bold cyan]Local Browser Automation Agent[/bold cyan]\n"
        "[white]Controls and autofills forms in your active Chrome/Edge session[/white]",
        border_style="cyan"
    ))

    parser = argparse.ArgumentParser(description="Local Browser Automation Agent")
    parser.add_argument("command", nargs="?", choices=["tabs", "inspect", "fill-aa02", "screenshot", "interactive"], default="interactive", help="Command to run")
    args = parser.parse_args()

    if args.command == "tabs":
        list_tabs()
    elif args.command == "inspect":
        inspect_page()
    elif args.command == "fill-aa02":
        fill_aa02_form()
    elif args.command == "screenshot":
        take_screenshot()
    else:
        # Interactive mode
        while True:
            console.print("\n[bold]Select an action:[/bold]")
            console.print("  [1] List Open Tabs")
            console.print("  [2] Inspect Form Elements on Active Tab")
            console.print("  [3] Autofill Companies House AA02 Form")
            console.print("  [4] Take Screenshot of Active Tab")
            console.print("  [5] Exit")

            choice = Prompt.ask("Enter choice", choices=["1", "2", "3", "4", "5"], default="3")

            if choice == "1":
                list_tabs()
            elif choice == "2":
                inspect_page()
            elif choice == "3":
                fill_aa02_form()
            elif choice == "4":
                take_screenshot()
            elif choice == "5":
                console.print("[cyan]Goodbye![/cyan]")
                break


if __name__ == "__main__":
    main()
