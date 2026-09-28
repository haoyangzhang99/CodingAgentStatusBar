"""
Exchange strategy - Handle exchange/conversation nodes.
"""

from .types import PanelContent, TreeNodeData, TranscriptData


class ExchangeStrategy:
    @staticmethod
    def handles() -> list[str]:
        return ["exchange", "user_turn", "conversation"]

    def get_content(self, node: TreeNodeData) -> PanelContent:
        node_type = node.node_type
        tokens_in = node.tokens_in
        tokens_out = node.tokens_out
        tokens_total = tokens_in + tokens_out

        if node_type == "exchange":
            return self._get_exchange_content(node, tokens_total)
        return self._get_conversation_content(node, tokens_total)

    def _get_exchange_content(
        self, node: TreeNodeData, tokens_total: int
    ) -> PanelContent:
        user = node.get("user", {}) or {}
        assistant = node.get("assistant", {}) or {}

        user_content = user.get("content", "") if user else ""
        assistant_content = assistant.get("content", "") if assistant else ""
        parts = assistant.get("parts", []) if assistant else []

        return PanelContent(
            breadcrumb=[],
            content_type="tabs",
            overview_data=None,
            transcript=TranscriptData(
                user_content=user_content,
                assistant_content=self._build_parts_summary(assistant_content, parts),
            ),
            available_tabs=[0],
            initial_tab=0,
        )

    def _get_conversation_content(
        self, node: TreeNodeData, tokens_total: int
    ) -> PanelContent:
        prompt_input = node.prompt_input or node.get("message_preview", "") or ""

        return PanelContent(
            breadcrumb=[],
            content_type="tabs",
            overview_data=None,
            transcript=TranscriptData(
                user_content=prompt_input,
                assistant_content="",
            ),
            available_tabs=[0],
            initial_tab=0,
        )

    def _build_parts_summary(self, base_content: str, parts: list) -> str:
        if not parts:
            return base_content or ""

        detailed = base_content or ""
        detailed += "\n\n--- Parts Summary ---\n"

        for p in parts[:20]:
            ptype = p.get("type", "")
            tool_name = p.get("tool_name", "")
            display_info = p.get("display_info", "")
            status = p.get("status", "")

            if tool_name:
                status_icon = (
                    "✓" if status == "completed" else "✗" if status == "error" else "◐"
                )
                info = f": {display_info[:60]}" if display_info else ""
                detailed += f"\n{status_icon} {tool_name}{info}"
            elif ptype == "text":
                content_preview = p.get("content", "")[:50]
                detailed += f"\n💭 {content_preview}..."

        if len(parts) > 20:
            detailed += f"\n... and {len(parts) - 20} more parts"

        return detailed
