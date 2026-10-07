"""The Settings window: a switch for each part of the dropdown."""

from typing import Any, Callable

from ..core.settings import SETTINGS

# Layout, in points.
WINDOW_WIDTH = 340
MARGIN = 20
HEADER_HEIGHT = 28
ROW_HEIGHT = 32
TEXT_HEIGHT = 17

TARGET_CLASS = "CodingAgentStatusBarSettingsTarget"


def target_class() -> Any:
    """An Objective-C class whose instances forward switch clicks to a Python function.
    Objective-C classes can't be defined twice, so a reloaded module reuses the first one."""
    import AppKit
    import objc

    try:
        return objc.lookUpClass(TARGET_CLASS)
    except objc.nosuchclass_error:
        pass

    class CodingAgentStatusBarSettingsTarget(AppKit.NSObject):
        def toggled_(self, sender):
            self.on_toggle(sender)

    return CodingAgentStatusBarSettingsTarget


def groups() -> list[tuple[str, list]]:
    """Settings by group, in the order they're listed."""
    grouped: dict[str, list] = {}
    for setting in SETTINGS:
        grouped.setdefault(setting.group, []).append(setting)
    return list(grouped.items())


def label(text: str, font: Any, color: Any) -> Any:
    import AppKit

    field = AppKit.NSTextField.labelWithString_(text)
    field.setFont_(font)
    field.setTextColor_(color)
    return field


class SettingsWindow:
    """A small window listing the dropdown's parts, each with an on/off switch.

    Closing it only hides it, so reopening it is instant.
    """

    def __init__(self, on_change: Callable[[str, bool], None]):
        import AppKit

        self._on_change = on_change
        self._switches: dict[str, Any] = {}
        self._target = target_class().alloc().init()
        self._target.on_toggle = self._toggled

        sections = groups()
        height = 2 * MARGIN + sum(
            HEADER_HEIGHT + ROW_HEIGHT * len(settings) for _, settings in sections
        )
        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (WINDOW_WIDTH, height)),
            AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Settings")
        self.window.setReleasedWhenClosed_(False)
        content = self.window.contentView()

        header_font = AppKit.NSFont.boldSystemFontOfSize_(AppKit.NSFont.smallSystemFontSize())
        body_font = AppKit.NSFont.systemFontOfSize_(AppKit.NSFont.systemFontSize())
        text_width = WINDOW_WIDTH - 2 * MARGIN
        y = height - MARGIN
        for group, settings in sections:
            y -= HEADER_HEIGHT
            header = label(group, header_font, AppKit.NSColor.secondaryLabelColor())
            header.setFrame_(((MARGIN, y + 4), (text_width, TEXT_HEIGHT)))
            content.addSubview_(header)
            for setting in settings:
                y -= ROW_HEIGHT
                switch = AppKit.NSSwitch.alloc().init()
                switch_width, switch_height = switch.fittingSize()
                switch.setFrame_((
                    (WINDOW_WIDTH - MARGIN - switch_width, y + (ROW_HEIGHT - switch_height) / 2),
                    (switch_width, switch_height),
                ))
                switch.setIdentifier_(setting.key)
                switch.setTarget_(self._target)
                switch.setAction_("toggled:")
                switch.setToolTip_(setting.help)
                switch.setAccessibilityLabel_(setting.label)
                name = label(setting.label, body_font, AppKit.NSColor.labelColor())
                name.setFrame_((
                    (MARGIN, y + (ROW_HEIGHT - TEXT_HEIGHT) / 2),
                    (text_width - switch_width - 8, TEXT_HEIGHT),
                ))
                name.setToolTip_(setting.help)
                content.addSubview_(name)
                content.addSubview_(switch)
                self._switches[setting.key] = switch

    def update(self, settings: dict[str, bool]) -> None:
        """Show the current settings; a switch whose app is turned off is grayed out."""
        import AppKit

        for setting in SETTINGS:
            switch = self._switches[setting.key]
            switch.setState_(
                AppKit.NSControlStateValueOn if settings[setting.key]
                else AppKit.NSControlStateValueOff
            )
            switch.setEnabled_(setting.requires is None or settings[setting.requires])

    def show(self, settings: dict[str, bool]) -> None:
        import AppKit

        self.update(settings)
        if not self.window.isVisible():
            self.window.center()
        # A menu bar app isn't active, so its window would open behind other apps' windows.
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.window.makeKeyAndOrderFront_(None)

    def _toggled(self, sender: Any) -> None:
        import AppKit

        self._on_change(str(sender.identifier()), sender.state() == AppKit.NSControlStateValueOn)
