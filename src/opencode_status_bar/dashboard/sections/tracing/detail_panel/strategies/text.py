"""
Text content strategy - Fallback for unknown node types.
"""

from .types import PanelContent, TreeNodeData, TranscriptData


class TextContentStrategy:
    @staticmethod
    def handles() -> list[str]:
        return []

    def get_content(self, node: TreeNodeData) -> PanelContent:
        prompt_input = node.prompt_input or ""
        prompt_output = node.prompt_output or ""

        return PanelContent(
            breadcrumb=[],
            content_type="tabs",
            overview_data=None,
            transcript=TranscriptData(
                user_content=prompt_input,
                assistant_content=prompt_output,
            ),
            available_tabs=[0],
            initial_tab=0,
        )
