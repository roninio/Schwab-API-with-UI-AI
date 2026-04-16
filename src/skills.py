"""
Skills — higher-level agent capabilities surfaced as quick-action shortcuts in the UI.

A Skill wraps one or more agent tools into a named, re-usable capability.
Each skill has:
  - A UI chip/button the user can click
  - A prompt_template that is pre-filled into the chat input
  - An optional input_hint shown as the textarea placeholder after the template
  - The underlying tool name(s) the agent will call to fulfil it
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillDefinition:
    name: str               # unique key
    label: str              # button label shown in the UI
    icon: str               # Material icon name
    description: str        # tooltip / sidebar description
    prompt_template: str    # pre-filled into the chat input when skill is clicked
    input_hint: str         # placeholder text shown after the template (what the user should type)
    tool_names: list[str]   # underlying agent tool(s) this skill relies on


SKILLS: list[SkillDefinition] = [
    SkillDefinition(
        name="chart_stock",
        label="Chart Stock",
        icon="show_chart",
        description="Create an interactive candlestick + volume chart for any symbol.",
        prompt_template="Create a stock chart for ",
        input_hint="symbol, e.g. SOFI  (optionally add: for the last 3 months)",
        tool_names=["create_stock_chart"],
    ),
    SkillDefinition(
        name="get_quote",
        label="Get Quote",
        icon="attach_money",
        description="Fetch the current price and quote data for a symbol.",
        prompt_template="What is the current price of ",
        input_hint="symbol, e.g. AAPL",
        tool_names=["get_quote"],
    ),
    SkillDefinition(
        name="show_positions",
        label="My Positions",
        icon="account_balance_wallet",
        description="Show all current open positions in the account.",
        prompt_template="Show me all my current open positions",
        input_hint="",   # no extra input needed — submit immediately
        tool_names=["get_positions"],
    ),
    SkillDefinition(
        name="show_orders",
        label="Recent Orders",
        icon="receipt_long",
        description="List recent orders placed in the account.",
        prompt_template="Show me my recent orders",
        input_hint="",
        tool_names=["get_account_orders"],
    ),
    SkillDefinition(
        name="buy_stock",
        label="Buy Stock",
        icon="trending_up",
        description="Place a limit order to buy shares (enable Buy Stock in Trading tools first).",
        prompt_template="Buy shares: ticker ",
        input_hint="e.g. AAPL — then say quantity and limit price (e.g. 10 shares at 185.50)",
        tool_names=["buy_stock"],
    ),
]

# Lookup by name
SKILL_MAP: dict[str, SkillDefinition] = {s.name: s for s in SKILLS}
