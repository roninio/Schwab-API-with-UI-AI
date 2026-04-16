"""
AI Trading Agent chat page.
Provides a conversational interface backed by Claude, OpenAI, or Gemini,
with per-tool permission toggles and skill quick-actions in a sidebar.
"""
from __future__ import annotations

from nicegui import run, ui
from nicegui_highcharts import highchart as hc_highchart  # noqa: F401  registers ui.highchart

from src.agent import TradingAgent
from src.agent_tools import ALL_TOOLS
from src.skills import SKILLS

_PROVIDERS = {
    "Claude (Anthropic)": "claude",
    "OpenAI GPT":         "openai",
    "Google Gemini":      "gemini",
}

_CATEGORY_CLASS = {
    "Market Data":  "agent-cat-market",
    "Account Info": "agent-cat-account",
    "Trading":      "agent-cat-trading",
    "Skills":       "agent-cat-skills",
}


def build_agent_page() -> None:
    agent = TradingAgent()
    agent.set_provider("gemini")

    ui.label("AI Trading Agent").classes("text-h5 mb-2 agent-page-title")

    with ui.row().classes("w-full no-wrap gap-4 items-start"):

        # ── Sidebar ──────────────────────────────────────────────────────────
        with ui.card().classes("agent-sidebar shrink-0 p-4 gap-2").style(
            "overflow-y: auto; max-height: 80vh"
        ):

            ui.label("Provider").classes("text-subtitle2 font-bold agent-muted")

            _default_provider = "gemini"
            _default_models = TradingAgent.MODELS[_default_provider]
            _state = {"provider": _default_provider}

            def on_model_change(e):
                agent.set_provider(_state["provider"], e.value)

            model_select = ui.select(
                _default_models,
                value=_default_models[0],
                label="Model",
                on_change=on_model_change,
            ).classes("w-full").props("outlined dense dark")

            def on_provider_change(e):
                pkey = _PROVIDERS[e.value]
                _state["provider"] = pkey
                models = TradingAgent.MODELS[pkey]
                model_select.options = models
                model_select.value = models[0]
                model_select.update()
                agent.set_provider(pkey, models[0])
                ui.notify(f"Switched to {e.value}", color="info", timeout=2000)

            ui.select(
                list(_PROVIDERS.keys()),
                value="Google Gemini",
                label="Provider",
                on_change=on_provider_change,
            ).classes("w-full").props("outlined dense dark")

            ui.separator()

            # ── Tool toggles grouped by category ─────────────────────────
            categories: dict[str, list] = {}
            for tool in ALL_TOOLS:
                categories.setdefault(tool.category, []).append(tool)

            for category, tools in categories.items():
                cat_cls = _CATEGORY_CLASS.get(category, "agent-cat-default")
                ui.label(category).classes(f"text-caption font-bold mt-2 {cat_cls}")

                for tool_def in tools:
                    def _make_toggle(tname: str):
                        def handler(e):
                            agent.set_tool_enabled(tname, e.value)
                        return handler

                    sw = ui.switch(
                        tool_def.label,
                        value=tool_def.enabled_by_default,
                        on_change=_make_toggle(tool_def.name),
                    ).props("dense dark")
                    if not tool_def.enabled_by_default:
                        sw.classes("agent-switch-off")

            ui.separator()
            ui.button("Clear History", on_click=lambda: (
                agent.clear_history(), _refresh_chat()
            ), icon="delete_sweep").classes("w-full mt-2").props("outline dense")

        # ── Chat area ─────────────────────────────────────────────────────────
        with ui.column().classes("flex-1 min-w-0 gap-2"):

            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Chat").classes("text-subtitle2 font-bold agent-muted")
                ui.button("New Chat", icon="add_comment", on_click=lambda: (
                    agent.clear_history(), _refresh_chat()
                )).props("outline dense").classes("agent-header-btn")

            chat_scroll = (
                ui.scroll_area()
                .classes("w-full agent-chat-scroll")
                .style("height: 60vh")
            )
            with chat_scroll:
                messages_col = ui.column().classes("w-full gap-2 p-3")

            # Thinking indicator (hidden by default)
            with ui.row().classes("items-center gap-2 hidden") as thinking_row:
                ui.spinner("dots", size="sm")
                ui.label("Agent is thinking…").classes("text-caption agent-muted")

            # ── Skill quick-action chips ──────────────────────────────────
            with ui.row().classes("w-full flex-wrap gap-2 pt-1"):
                for skill in SKILLS:
                    def _make_skill_handler(s):
                        def handler():
                            if s.input_hint:
                                # Pre-fill template; user types the rest
                                msg_input.value = s.prompt_template
                                msg_input.run_method("focus")
                            else:
                                # No extra input needed — submit immediately
                                msg_input.value = s.prompt_template
                                ui.timer(0.05, lambda: on_send(), once=True)
                        return handler

                    ui.button(skill.label, icon=skill.icon, on_click=_make_skill_handler(skill)) \
                        .props("outline dense") \
                        .classes("agent-skill-btn") \
                        .tooltip(skill.description)

            # ── Input row ────────────────────────────────────────────────
            with ui.row().classes("w-full no-wrap gap-2 items-end"):
                msg_input = (
                    ui.textarea(placeholder="Ask anything, or click a skill above…")
                    .props("outlined dense autogrow dark")
                    .classes("flex-1")
                    .style("max-height: 120px")
                )
                send_btn = ui.button("Send", icon="send").props("unelevated")

    # ── Message rendering ────────────────────────────────────────────────────

    def _refresh_chat() -> None:
        messages_col.clear()
        with messages_col:
            for turn in agent.history:
                if turn.role == "user":
                    with ui.row().classes("justify-end w-full"):
                        ui.label(turn.text or "").classes(
                            "rounded-xl px-3 py-2 agent-user-bubble"
                        ).style("max-width: 75%")

                elif turn.role == "assistant" and turn.text:
                    with ui.row().classes("justify-start w-full"):
                        with ui.card().classes(
                            "rounded-xl px-3 py-2 agent-assistant-card"
                        ).style("max-width: 75%"):
                            ui.markdown(turn.text)

                elif turn.role == "assistant" and turn.tool_calls:
                    names = ", ".join(tc["name"] for tc in turn.tool_calls)
                    with ui.row().classes("justify-start w-full"):
                        ui.label(f"⚙ Calling: {names}").classes(
                            "text-caption agent-tool-caption"
                        )

                elif turn.role == "tool_result":
                    for tr in (turn.tool_results or []):
                        result = tr.get("result", {})
                        if isinstance(result, dict) and result.get("__chart_type__") == "highcharts_stock":
                            with ui.column().classes("w-full gap-1"):
                                ui.label(f"📈 {result.get('symbol', '')} Chart").classes(
                                    "text-caption font-medium agent-chart-cap"
                                )
                                ui.highchart(
                                    result["options"],
                                    type="stockChart",
                                    extras=["stock"],
                                ).classes("w-full")
                        else:
                            with ui.row().classes("justify-start w-full"):
                                ui.label(f"↩ {tr['name']}").classes(
                                    "text-caption agent-tool-link"
                                ).tooltip(str(result)[:600])

        chat_scroll.scroll_to(percent=1.0)

    # ── Send handler ─────────────────────────────────────────────────────────

    async def on_send() -> None:
        msg = (msg_input.value or "").strip()
        if not msg:
            ui.notify("Please enter a message", color="warning", timeout=2000)
            return

        msg_input.value = ""
        msg_input.disable()
        send_btn.disable()
        thinking_row.classes(remove="hidden")
        _refresh_chat()

        try:
            await run.io_bound(agent.run, msg)
        except Exception as exc:
            ui.notify(f"Agent error: {exc}", color="negative", timeout=6000)
        finally:
            thinking_row.classes("hidden")
            msg_input.enable()
            send_btn.enable()
            _refresh_chat()

    send_btn.on("click", on_send)
    msg_input.on("keydown.enter.prevent", on_send)
