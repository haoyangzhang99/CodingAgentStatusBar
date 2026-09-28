"""
Menu Builder - Constructs rumps menu items for OpenCode Status Bar
"""

from datetime import datetime
from typing import Optional, Callable, Any

import rumps

from ..core.models import State, SessionStatus, Usage, Agent
from ..security.analyzer import analyze_command, RiskLevel


# Truncation limits for menu items
TITLE_MAX_LENGTH = 40
TOOL_ARG_MAX_LENGTH = 30
TODO_CURRENT_MAX_LENGTH = 35
TODO_PENDING_MAX_LENGTH = 30


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
    """Create a menu item, adding a tooltip if text exceeds max_length.

    Args:
        text: The full text to display
        max_length: Maximum length before truncation
        prefix: Prefix to prepend (icons, indentation)
        callback: Optional click callback

    Returns:
        A rumps.MenuItem with tooltip set if text was truncated
    """
    is_truncated = len(text) > max_length

    if is_truncated:
        display_text = text[: max_length - 3] + "..."
    else:
        display_text = text

    item = rumps.MenuItem(f"{prefix}{display_text}", callback=callback)

    # Set native macOS tooltip only if truncated
    if is_truncated:
        item._menuitem.setToolTip_(text)

    return item


class MenuBuilder:
    """Builds menu items for the OpenCode Status Bar app"""

    def __init__(self, port_names_cache: dict, port_names_limit: int = 50):
        """Initialize with a cache for port names.

        Args:
            port_names_cache: Dict mapping port -> last known agent name
            port_names_limit: Max cached names before cleanup
        """
        self._port_names = port_names_cache
        self._port_names_limit = port_names_limit

    def build_dynamic_items(
        self,
        state: Optional[State],
        usage: Optional[Usage],
        focus_callback: Callable[[str], None],
        alert_callback: Callable[[Any], None],
    ) -> list:
        """Build dynamic menu items for instances and usage.

        Args:
            state: Current application state
            usage: Current usage data
            focus_callback: Callback to focus terminal (takes tty string)
            alert_callback: Callback to track security alerts

        Returns:
            List of rumps.MenuItem objects
        """
        items = []

        if state is None or not state.connected:
            items.append(rumps.MenuItem("No OpenCode instances"))
            return items

        # Clean up port name cache (keep only active ports)
        active_ports = {inst.port for inst in state.instances}
        self._port_names = {
            p: n for p, n in self._port_names.items() if p in active_ports
        }

        # Build items for each instance
        for instance in state.instances:
            tty = instance.tty

            # Separate main agents from sub-agents
            main_agents = [a for a in instance.agents if not a.is_subagent]
            sub_agents_map: dict[str, list[Agent]] = {}
            for a in instance.agents:
                if a.is_subagent and a.parent_id is not None:
                    if a.parent_id not in sub_agents_map:
                        sub_agents_map[a.parent_id] = []
                    sub_agents_map[a.parent_id].append(a)

            if main_agents:
                # Cache the name
                self._port_names[instance.port] = main_agents[0].title

                # Rotate cache if too large
                if len(self._port_names) > self._port_names_limit:
                    keys = list(self._port_names.keys())
                    for k in keys[: len(keys) // 2]:
                        del self._port_names[k]

                # Build agent items
                for agent in main_agents:
                    items.extend(
                        self.build_agent_items(
                            agent, tty, 0, focus_callback, alert_callback
                        )
                    )
                    for sub_agent in sub_agents_map.get(agent.id, []):
                        items.extend(
                            self.build_agent_items(
                                sub_agent, tty, 1, focus_callback, alert_callback
                            )
                        )
            else:
                # Instance idle
                display_name = self._port_names.get(
                    instance.port, f"Port {instance.port}"
                )

                def make_focus_cb(t):
                    def cb(_):
                        if t:
                            focus_callback(t)

                    return cb

                idle_item = rumps.MenuItem(
                    f"{display_name} (idle)", callback=make_focus_cb(tty)
                )
                set_menu_symbol(idle_item, "moon.zzz")
                items.append(idle_item)

        # Add usage items
        if usage:
            items.append(None)  # separator
            items.extend(self.build_usage_items(usage))

        return items

    def build_agent_items(
        self,
        agent: Agent,
        tty: str,
        indent: int,
        focus_callback: Callable[[str], None],
        alert_callback: Callable[[Any], None],
    ) -> list:
        """Build menu items for an agent.

        Args:
            agent: The agent to build items for
            tty: TTY string for terminal focus
            indent: Indentation level (0 for main, 1 for sub-agent)
            focus_callback: Callback to focus terminal
            alert_callback: Callback to track security alerts

        Returns:
            List of rumps.MenuItem objects
        """
        items = []
        # Symbols match the menu bar: terminal = working, checkmark = done,
        # question mark = waiting for an answer, hand = waiting for approval.
        approval = any(tool.may_need_permission for tool in agent.tools)

        # Agent icon and callback
        if indent > 0:
            # Sub-agent icons (never have ask_user)
            symbol = "circle.fill" if agent.status == SessionStatus.BUSY else "circle"
            callback = None
        else:
            # Main agent icons
            if agent.has_pending_ask_user:
                symbol = "questionmark.circle"
            elif approval:
                symbol = "hand.raised"
            elif agent.status == SessionStatus.BUSY:
                symbol = "terminal"
            else:
                symbol = "checkmark.circle"

            def make_focus_cb(t):
                def cb(_):
                    if t:
                        focus_callback(t)

                return cb

            callback = make_focus_cb(tty)

        # Clean title
        title = agent.title
        if "(@" in title:
            title = title.split("(@")[0].strip()

        # Create agent item
        agent_item = truncate_with_tooltip(title, TITLE_MAX_LENGTH, callback=callback)
        set_menu_symbol(agent_item, symbol)
        set_menu_indent(agent_item, indent)
        items.append(agent_item)

        # Tools with security analysis and permission detection
        if agent.tools:
            for tool in agent.tools:
                alert = None
                if tool.name.lower() in ("bash", "shell", "execute"):
                    alert = analyze_command(tool.arg, tool.name)
                    alert.agent_id = agent.id
                    alert.agent_title = agent.title

                    if alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                        alert_callback(alert)

                # Determine tool symbol: permission > security > default
                if tool.may_need_permission:
                    tool_symbol = "hand.raised"
                elif alert and alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    tool_symbol = "exclamationmark.triangle"
                else:
                    tool_symbol = "wrench.and.screwdriver"

                full_tool_text = f"{tool.name}: {tool.arg}" if tool.arg else tool.name

                item = truncate_with_tooltip(full_tool_text, TOOL_ARG_MAX_LENGTH)
                set_menu_symbol(item, tool_symbol)
                set_menu_indent(item, indent + 1)

                # Set tooltip based on state
                if tool.may_need_permission:
                    elapsed_sec = tool.elapsed_ms // 1000
                    if elapsed_sec >= 60:
                        mins, secs = divmod(elapsed_sec, 60)
                        duration = f"{mins}m {secs}s"
                    else:
                        duration = f"{elapsed_sec}s"
                    tooltip = f"May be waiting for permission (running {duration})\n\n{tool.arg}"
                    item._menuitem.setToolTip_(tooltip)
                elif alert and alert.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    tooltip = (
                        f"{alert.reason}\nScore: {alert.score}/100\n\n{tool.arg}"
                    )
                    item._menuitem.setToolTip_(tooltip)

                items.append(item)

        # Pending ask_user (MCP Notify awaiting response)
        if agent.has_pending_ask_user and agent.ask_user_title:
            item = truncate_with_tooltip(agent.ask_user_title, TITLE_MAX_LENGTH)
            set_menu_symbol(item, "text.bubble")
            set_menu_indent(item, indent + 1)
            item._menuitem.setToolTip_(
                f"Awaiting user response\n\n{agent.ask_user_title}"
            )
            items.append(item)

        # Todos
        if agent.todos:
            if agent.todos.in_progress > 0 and agent.todos.current_label:
                item = truncate_with_tooltip(
                    agent.todos.current_label, TODO_CURRENT_MAX_LENGTH
                )
                set_menu_symbol(item, "play.circle")
                set_menu_indent(item, indent + 1)
                items.append(item)

            if agent.todos.pending > 0 and agent.todos.next_label:
                suffix = (
                    f" (+{agent.todos.pending - 1})" if agent.todos.pending > 1 else ""
                )
                full_label = agent.todos.next_label + suffix
                item = truncate_with_tooltip(full_label, TODO_PENDING_MAX_LENGTH)
                set_menu_symbol(item, "hourglass")
                set_menu_indent(item, indent + 1)
                items.append(item)

        return items

    def build_usage_items(self, usage: Usage) -> list:
        """Build usage display items.

        Args:
            usage: Usage data

        Returns:
            List of rumps.MenuItem objects
        """
        items = []

        if usage.error:
            items.append(rumps.MenuItem(f"⚠️ Usage: {usage.error}"))
            return items

        five_h = usage.five_hour.utilization
        seven_d = usage.seven_day.utilization

        # Color icon based on usage
        if five_h >= 90:
            icon = "🔴"
        elif five_h >= 70:
            icon = "🟠"
        elif five_h >= 50:
            icon = "🟡"
        else:
            icon = "🟢"

        # Session reset time
        session_reset = ""
        if usage.five_hour.resets_at:
            try:
                reset_time = datetime.fromisoformat(
                    usage.five_hour.resets_at.replace("Z", "+00:00")
                )
                now = datetime.now(reset_time.tzinfo)
                diff = reset_time - now
                minutes = int(diff.total_seconds() / 60)
                if minutes > 60:
                    session_reset = f" (reset {minutes // 60}h{minutes % 60:02d}m)"
                elif minutes > 0:
                    session_reset = f" (reset {minutes}m)"
            except Exception:
                pass  # nosec B110 - invalid date format is ignored

        # Weekly reset time
        weekly_reset = ""
        if usage.seven_day.resets_at:
            try:
                reset_time = datetime.fromisoformat(
                    usage.seven_day.resets_at.replace("Z", "+00:00")
                )
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                day_name = days[reset_time.weekday()]
                weekly_reset = f" (reset {day_name} {reset_time.hour}h)"
            except Exception:
                pass  # nosec B110 - invalid date format is ignored

        items.append(rumps.MenuItem(f"{icon} Session: {five_h}%{session_reset}"))
        items.append(rumps.MenuItem(f"📅 Weekly: {seven_d}%{weekly_reset}"))
        items.append(
            rumps.MenuItem(
                "🌐 Open Claude Usage",
                callback=lambda _: __import__("subprocess").run(  # nosec B404 B603 B607
                    ["open", "https://console.anthropic.com/settings/usage"]
                ),
            )
        )

        return items
