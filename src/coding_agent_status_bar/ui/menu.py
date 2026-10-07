"""
Menu Builder - Constructs rumps menu items for Coding Agent Status Bar
"""

from typing import Any, Callable, Optional

import rumps

from ..core.models import Agent, HookState, SessionStatus, State, Usage, UsageLimit


# Truncation limits for menu items
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30

# Usage row layout, in points. Text fields pad their text by 2, so the inset puts the label's
# text where menu titles and icons start.
USAGE_ROW_SIZE = (260, 20)
USAGE_INSET = 14
USAGE_NAME_WIDTH = 52
USAGE_PERCENT_WIDTH = 58
USAGE_TEXT_HEIGHT = 14
USAGE_BAR_HEIGHT = 6
USAGE_GAP = 6

# How each app's usage numbers stay current, shown as the usage rows' tooltip.
USAGE_SOURCES = {
    "Codex": "Codex updates it after each reply, in the app and the terminal.",
    "Claude Code": (
        "Updated after each reply in Claude Code in a terminal. Use in the Claude app or on "
        "claude.ai counts too, but shows only after your next terminal reply."
    ),
}


def tint_yellow(image: Any, size: tuple) -> Any:
    """A yellow copy of a template image, for things that need you. Only the image's pixels
    are colored, so text next to it keeps its native color."""
    import AppKit

    colored = AppKit.NSImage.alloc().initWithSize_(size)
    colored.lockFocus()
    try:
        rect = ((0, 0), size)
        image.drawInRect_fromRect_operation_fraction_(
            rect, AppKit.NSZeroRect, AppKit.NSCompositingOperationSourceOver, 1.0
        )
        AppKit.NSColor.systemYellowColor().set()
        AppKit.NSRectFillUsingOperation(rect, AppKit.NSCompositingOperationSourceIn)
    finally:
        colored.unlockFocus()
    colored.setTemplate_(False)
    return colored


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


def usage_label(text: str, font: Any, alignment: int) -> Any:
    import AppKit

    field = AppKit.NSTextField.labelWithString_(text)
    field.setFont_(font)
    field.setTextColor_(AppKit.NSColor.secondaryLabelColor())
    field.setAlignment_(alignment)
    return field


def usage_view(limit: UsageLimit, description: str, tooltip: str) -> Any:
    """A usage row's view: "5-hour", a bar of what's left, and "99% left", in small gray text.

    The menu draws neither a highlight nor a grayed-out look for an item that has a view and no
    action, so the row reads as information, not as something to click. The bar is gray, or
    yellow while the limit is low. If the menu is wider, the bar grows and its fill keeps the
    same share.
    """
    import AppKit

    width, height = USAGE_ROW_SIZE
    view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (width, height)))
    view.setAutoresizingMask_(AppKit.NSViewWidthSizable)
    size = AppKit.NSFont.smallSystemFontSize()
    text_y = (height - USAGE_TEXT_HEIGHT) / 2

    name = usage_label(limit.name, AppKit.NSFont.systemFontOfSize_(size), AppKit.NSTextAlignmentLeft)
    name.setFrame_(((USAGE_INSET, text_y), (USAGE_NAME_WIDTH, USAGE_TEXT_HEIGHT)))
    digits = AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(size, AppKit.NSFontWeightRegular)
    percent = usage_label(f"{limit.left}% left", digits, AppKit.NSTextAlignmentRight)
    percent_x = width - USAGE_INSET - USAGE_PERCENT_WIDTH
    percent.setFrame_(((percent_x, text_y), (USAGE_PERCENT_WIDTH, USAGE_TEXT_HEIGHT)))
    percent.setAutoresizingMask_(AppKit.NSViewMinXMargin)

    bar_x = USAGE_INSET + USAGE_NAME_WIDTH + USAGE_GAP
    bar_width = percent_x - USAGE_GAP - bar_x
    bar = AppKit.NSView.alloc().initWithFrame_(
        ((bar_x, (height - USAGE_BAR_HEIGHT) / 2), (bar_width, USAGE_BAR_HEIGHT))
    )
    bar.setAutoresizingMask_(AppKit.NSViewWidthSizable)
    # At least as wide as it is tall, so a nearly empty bar still shows a rounded dot.
    filled = max(USAGE_BAR_HEIGHT, bar_width * limit.left / 100) if limit.left > 0 else 0
    fill_color = (
        AppKit.NSColor.systemYellowColor() if limit.low else AppKit.NSColor.secondaryLabelColor()
    )
    for box_width, color, mask in (
        (bar_width, AppKit.NSColor.quaternaryLabelColor(), AppKit.NSViewWidthSizable),
        # A flexible width and right margin share any extra width by their sizes.
        (filled, fill_color, AppKit.NSViewWidthSizable | AppKit.NSViewMaxXMargin),
    ):
        box = AppKit.NSBox.alloc().initWithFrame_(((0, 0), (box_width, USAGE_BAR_HEIGHT)))
        box.setBoxType_(AppKit.NSBoxCustom)
        box.setBorderWidth_(0)
        box.setCornerRadius_(USAGE_BAR_HEIGHT / 2)
        box.setFillColor_(color)
        box.setAutoresizingMask_(mask)
        bar.addSubview_(box)

    for subview in (name, bar, percent):
        view.addSubview_(subview)
    view.setToolTip_(tooltip or None)
    view.setAccessibilityElement_(True)
    view.setAccessibilityRole_(AppKit.NSAccessibilityStaticTextRole)
    view.setAccessibilityLabel_(description)
    return view


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
        """Build the OpenCode section: a header, then every OpenCode process and its
        recent sessions.

        Args:
            state: Current application state
            on_select: rumps callback for clicking a session row
        """
        # Without a callback, rumps shows the header as a disabled label.
        items: list = [rumps.MenuItem("OpenCode")]

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
                cached_name = self._port_names.get(instance.port)
                idle_title = f"{cached_name} (idle)" if cached_name else "OpenCode idle"
                idle_item = rumps.MenuItem(idle_title, callback=on_select)
                set_menu_symbol(idle_item, "moon.zzz")
                items.append(idle_item)

        return items

    def build_hook_items(
        self,
        state: Optional[HookState],
        app_name: str,
        on_select: Optional[Callable] = None,
    ) -> list:
        """Build the section for Codex or Claude Code: a header, its usage limits and
        its recent sessions, or nothing while the app isn't running.

        Args:
            state: Current state of the app
            app_name: Header and label text, such as "Codex"
            on_select: rumps callback for clicking a session row
        """
        if state is None or not state.running:
            return []
        # Without a callback, rumps shows the header as a disabled label.
        items: list = [rumps.MenuItem(app_name)]
        items.extend(self.build_usage_items(state.usage, app_name))
        if not state.sessions:
            idle_item = rumps.MenuItem(f"{app_name} idle", callback=on_select)
            set_menu_symbol(idle_item, "moon.zzz")
            items.append(idle_item)
        for session in state.sessions:
            items.extend(self.build_agent_items(session, 0, on_select, app_name=app_name))
        return items

    def build_usage_items(self, usage: Optional[Usage], app_name: str) -> list:
        """One row per usage limit: a small label, a bar of what's left, and the percent.
        The rows can't be clicked; their title, such as "5-hour limit: 99% left", is only
        shown if the bar can't be drawn."""
        if usage is None:
            return []
        items = []
        for limit in usage.limits:
            # Without a callback the row is disabled; its view keeps it from looking grayed out.
            item = rumps.MenuItem(f"{limit.name} limit: {limit.left}% left")
            try:
                view = usage_view(limit, f"{app_name} {item.title}", USAGE_SOURCES.get(app_name, ""))
                item._menuitem.setView_(view)
            except Exception:
                # Never break the menu over a drawing problem; the title still shows.
                pass
            items.append(item)
        return items

    def build_agent_items(
        self,
        agent: Agent,
        indent: int,
        on_select: Optional[Callable] = None,
        app_name: str = "OpenCode",
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
            item._menuitem.setToolTip_(f"{app_name} is waiting for you to approve a request")
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
