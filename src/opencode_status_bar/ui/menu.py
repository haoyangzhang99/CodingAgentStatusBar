"""
Menu Builder - Constructs rumps menu items for OpenCode Status Bar
"""

from typing import Any, Callable, Optional

import rumps

from ..core.models import Agent, SessionStatus, State


# Truncation limits for menu items
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30


def set_menu_symbol(item: Any, symbol: str) -> None:
    """Give a menu item a monochrome SF Symbol that adapts to light/dark menus."""
    item.symbol_name = symbol
    try:
        import AppKit

        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol, None
        )
        if image is None:
            return
        image.setTemplate_(True)
        item._menuitem.setImage_(image)
    except Exception:
        # A missing icon must never break the menu; the text still shows.
        pass


def set_menu_indent(item: Any, level: int) -> None:
    """Indent natively; leading spaces would sit between the icon and the text."""
    if level <= 0:
        return
    try:
        item._menuitem.setIndentationLevel_(level)
    except Exception:
        pass


def truncate_with_tooltip(
    text: str, max_length: int, prefix: str = "", callback: Optional[Callable] = None
) -> rumps.MenuItem:
    """Create a menu item, adding a tooltip with the full text if truncated."""
    is_truncated = len(text) > max_length
    display_text = text[: max_length - 3] + "..." if is_truncated else text

    item = rumps.MenuItem(f"{prefix}{display_text}", callback=callback)
    if is_truncated:
        item._menuitem.setToolTip_(text)
    return item


class MenuBuilder:
    """Builds the dropdown's session rows."""

    def __init__(self, port_names_cache: dict, port_names_limit: int = 50):
        """
        Args:
            port_names_cache: Instance key -> last known session title, used to
                label an OpenCode process whose sessions have all gone quiet
            port_names_limit: Max cached names before cleanup
        """
        self._port_names = port_names_cache
        self._port_names_limit = port_names_limit

    def build_dynamic_items(
        self, state: Optional[State], on_select: Optional[Callable] = None
    ) -> list:
        """Build rows for every OpenCode process and its recent sessions.

        Args:
            state: Current application state
            on_select: rumps callback for clicking a session row
        """
        items: list = []

        if state is None or not state.connected:
            items.append(rumps.MenuItem("No OpenCode instances"))
            return items

        # Keep cached names only for processes that are still running
        active_ports = {inst.port for inst in state.instances}
        self._port_names = {
            p: n for p, n in self._port_names.items() if p in active_ports
        }

        for instance in state.instances:
            main_agents = [a for a in instance.agents if not a.is_subagent]
            sub_agents_map: dict[str, list[Agent]] = {}
            for a in instance.agents:
                if a.is_subagent and a.parent_id is not None:
                    sub_agents_map.setdefault(a.parent_id, []).append(a)

            if main_agents:
                self._port_names[instance.port] = main_agents[0].title
                if len(self._port_names) > self._port_names_limit:
                    keys = list(self._port_names.keys())
                    for k in keys[: len(keys) // 2]:
                        del self._port_names[k]

                for agent in main_agents:
                    items.extend(self.build_agent_items(agent, 0, on_select))
                    for sub_agent in sub_agents_map.get(agent.id, []):
                        items.extend(self.build_agent_items(sub_agent, 1, on_select))
            else:
                display_name = self._port_names.get(
                    instance.port, f"Port {instance.port}"
                )
                idle_item = rumps.MenuItem(f"{display_name} (idle)", callback=on_select)
                set_menu_symbol(idle_item, "moon.zzz")
                items.append(idle_item)

        return items

    def build_agent_items(
        self, agent: Agent, indent: int, on_select: Optional[Callable] = None
    ) -> list:
        """Build the row for one session, plus rows for what it's waiting on.

        Symbols match the menu bar: terminal = working, checkmark = done,
        question mark = waiting for an answer, hand = waiting for approval.
        """
        items = []
        approval = any(tool.may_need_permission for tool in agent.tools)

        if indent > 0:
            # Sub-agents: filled circle while working; rows are not clickable
            symbol = "circle.fill" if agent.status == SessionStatus.BUSY else "circle"
            callback = None
        else:
            if agent.has_pending_ask_user:
                symbol = "questionmark.circle"
            elif approval:
                symbol = "hand.raised"
            elif agent.status == SessionStatus.BUSY:
                symbol = "terminal"
            else:
                symbol = "checkmark.circle"
            callback = on_select

        # Drop branch info such as "Title (@feature/branch)"
        title = agent.title
        if "(@" in title:
            title = title.split("(@")[0].strip()

        agent_item = truncate_with_tooltip(title, TITLE_MAX_LENGTH, callback=callback)
        set_menu_symbol(agent_item, symbol)
        set_menu_indent(agent_item, indent)
        items.append(agent_item)

        for tool in agent.tools:
            if not tool.may_need_permission:
                continue
            item = truncate_with_tooltip(tool.name, TOOL_ARG_MAX_LENGTH)
            set_menu_symbol(item, "hand.raised")
            set_menu_indent(item, indent + 1)
            item._menuitem.setToolTip_("OpenCode is waiting for you to approve a request")
            items.append(item)

        if agent.has_pending_ask_user and agent.ask_user_title:
            item = truncate_with_tooltip(agent.ask_user_title, TITLE_MAX_LENGTH)
            set_menu_symbol(item, "text.bubble")
            set_menu_indent(item, indent + 1)
            item._menuitem.setToolTip_(
                f"Awaiting user response\n\n{agent.ask_user_title}"
            )
            items.append(item)

        return items
