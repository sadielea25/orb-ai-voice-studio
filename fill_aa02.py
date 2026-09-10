"""
fill_aa02.py
Autofills the Companies House AA02 (Dormant Company Accounts) form
on your active logged-in browser session.
"""

import sys
import argparse
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from browser_connector import BrowserConnector

console = Console()


def fill_aa02_form(
    unpaid_capital: str = "1",
    cash_in_bank: str = "0",
    num_shares: str = "1",
    share_class: str = "Ordinary",
    share_value: str = "1",
    approval_date: str = None,
    click_validate: bool = False
):
    if approval_date is None:
        approval_date = datetime.now().strftime("%d/%m/%Y")

    console.print(Panel.fit("[bold blue]Companies House AA02 Dormant Accounts Autofiller[/bold blue]"))
    
    summary_table = Table(title="Values to Fill")
    summary_table.add_column("Field", style="cyan")
    summary_table.add_column("Value", style="green")
    summary_table.add_row("Called up share capital not paid", unpaid_capital)
    summary_table.add_row("Cash at bank and in hand", cash_in_bank)
    summary_table.add_row("Share Class", share_class)
    summary_table.add_row("Number of Shares", num_shares)
    summary_table.add_row("Value of Each Share", share_value)
    summary_table.add_row("Current Period Total", str(int(num_shares) * int(share_value) if num_shares.isdigit() and share_value.isdigit() else "1"))
    summary_table.add_row("Approval Date", approval_date)
    console.print(summary_table)

    connector = BrowserConnector()
    try:
        console.print("\n[yellow]Connecting to active browser on port 9222...[/yellow]")
        connector.connect()

        # Find the Companies House WebFiling tab
        page = connector.find_page_by_url("companieshouse.gov.uk")
        if not page:
            page = connector.get_active_or_first_page()
            console.print(f"[yellow]Note: Targeted active tab: {page.url}[/yellow]")
        else:
            console.print(f"[green]Found Companies House tab: {page.title()} ({page.url})[/green]")

        console.print("\n[cyan]Inspecting and populating form elements...[/cyan]")

        # 1. Fill Assets: Called up share capital not paid & Cash at bank
        # Find input associated with 'Called up share capital not paid'
        page.evaluate(f"""() => {{
            // Helper to find inputs by preceding text or label
            function findInputByText(textMatch) {{
                const allElements = Array.from(document.querySelectorAll('label, td, div, span, p'));
                for (const el of allElements) {{
                    if (el.textContent.includes(textMatch)) {{
                        // Check if parent contains input
                        let container = el.closest('tr') || el.closest('.form-group') || el.parentElement;
                        if (container) {{
                            const input = container.querySelector('input[type="text"], input:not([type])');
                            if (input) return input;
                        }}
                    }}
                }}
                return null;
            }}

            // 1. Called up share capital not paid
            const unpaidInput = findInputByText('Called up share capital not paid') || document.querySelector('input[name*="unpaid"], input[id*="unpaid"], input[name*="calledUpShareCapitalNotPaid"]');
            if (unpaidInput) {{
                unpaidInput.value = '{unpaid_capital}';
                unpaidInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                unpaidInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // 2. Cash at bank and in hand
            const cashInput = findInputByText('Cash at bank and in hand') || document.querySelector('input[name*="cash"], input[id*="cash"]');
            if (cashInput) {{
                cashInput.value = '{cash_in_bank}';
                cashInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                cashInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // 3. Issued Share Capital Inputs
            // Find the table/row for Issued share capital
            const shareClassRows = Array.from(document.querySelectorAll('tr, .form-group, div')).filter(r => 
                r.textContent.includes('Number of shares') || r.querySelector('input[name*="share"]')
            );
            
            // Try specific input mapping for Issued Share Capital
            const allTextInputs = Array.from(document.querySelectorAll('input[type="text"], input:not([type])'));
            
            // Fill share capital fields by their visible placeholders/labels/classes
            const shareInputs = allTextInputs.filter(inp => {{
                const parentText = inp.parentElement ? inp.parentElement.textContent : '';
                const containerText = inp.closest('tr, div') ? inp.closest('tr, div').textContent : '';
                return parentText.includes('share') || containerText.includes('share') || containerText.includes('Number') || containerText.includes('class');
            }});

            // Fallback to searching all inputs on the page by order if in table
            const shareSection = Array.from(document.querySelectorAll('div, table, fieldset')).find(el => 
                el.textContent.includes('Issued share capital')
            );

            if (shareSection) {{
                const inputs = shareSection.querySelectorAll('input[type="text"], input:not([type])');
                if (inputs.length >= 4) {{
                    // inputs: [Number of shares, share class, Value of each share, Current period]
                    inputs[0].value = '{num_shares}';
                    inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));

                    inputs[1].value = '{share_class}';
                    inputs[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[1].dispatchEvent(new Event('change', {{ bubbles: true }}));

                    inputs[2].value = '{share_value}';
                    inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[2].dispatchEvent(new Event('change', {{ bubbles: true }}));

                    inputs[3].value = '{str(int(num_shares) * int(share_value) if num_shares.isdigit() and share_value.isdigit() else "1")}';
                    inputs[3].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inputs[3].dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}

            // 4. Approval Date
            const dateInput = findInputByText('Date of approval of accounts') || 
                              findInputByText('approval') ||
                              document.querySelector('input[name*="approvalDate"], input[id*="approvalDate"], input[name*="date"]');
            if (dateInput) {{
                dateInput.value = '{approval_date}';
                dateInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                dateInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // 5. Ensure all statutory checkboxes are checked
            const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
            checkboxes.forEach(cb => {{
                const labelText = (cb.parentElement ? cb.parentElement.textContent : '') + (cb.closest('div') ? cb.closest('div').textContent : '');
                if (labelText.includes('section 476') || 
                    labelText.includes('accounting records') || 
                    labelText.includes('small companies')) {{
                    cb.checked = true;
                    cb.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }});
        }}""")

        console.print("[green]✔ Form fields successfully filled![/green]")

        if click_validate:
            console.print("\n[yellow]Clicking 'VALIDATE AND CONTINUE'...[/yellow]")
            page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('input[type="submit"], button')).find(b => 
                    b.value.includes('VALIDATE') || b.textContent.includes('VALIDATE') || b.value.includes('Continue') || b.textContent.includes('Continue')
                );
                if (btn) btn.click();
            }""")
            console.print("[green]✔ Clicked Validate button.[/green]")
        else:
            console.print("\n[bold green]Done! Review the filled form in your browser window.[/bold green]")
            console.print("When you're ready, click [bold blue]'VALIDATE AND CONTINUE'[/bold blue] in your browser.")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        connector.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autofill Companies House AA02 Dormant Accounts Form")
    parser.add_argument("--unpaid", default="1", help="Called up share capital not paid (default: 1)")
    parser.add_argument("--cash", default="0", help="Cash at bank and in hand (default: 0)")
    parser.add_argument("--shares", default="1", help="Number of shares (default: 1)")
    parser.add_argument("--class", dest="share_class", default="Ordinary", help="Share class (default: Ordinary)")
    parser.add_argument("--value", default="1", help="Nominal value per share (default: 1)")
    parser.add_argument("--date", default=None, help="Date of approval DD/MM/YYYY (default: today)")
    parser.add_argument("--validate", action="store_true", help="Automatically click 'VALIDATE AND CONTINUE'")

    args = parser.parse_args()

    fill_aa02_form(
        unpaid_capital=args.unpaid,
        cash_in_bank=args.cash,
        num_shares=args.shares,
        share_class=args.share_class,
        share_value=args.value,
        approval_date=args.date,
        click_validate=args.validate
    )
