import factory
from datetime import datetime

from opencode_status_bar.core.models import (
    Agent,
    Instance,
    Tool,
    AgentTodos,
    SessionStatus,
)


class ToolFactory(factory.Factory):
    class Meta:
        model = Tool

    name = factory.Iterator(
        ["bash", "read", "write", "edit", "grep", "lsp_diagnostics"]
    )
    arg = factory.Faker("word")
    elapsed_ms = factory.Faker("random_int", min=0, max=5000)


class AgentTodosFactory(factory.Factory):
    class Meta:
        model = AgentTodos

    pending = factory.Faker("random_int", min=0, max=5)
    in_progress = factory.Faker("random_int", min=0, max=2)
    current_label = factory.Faker("sentence", nb_words=4)
    next_label = factory.Faker("sentence", nb_words=4)


class AgentFactory(factory.Factory):
    class Meta:
        model = Agent

    id = factory.Sequence(lambda n: f"agent_{n}")
    title = factory.Faker("job")
    dir = factory.Faker("word")
    full_dir = factory.Faker("file_path", depth=3)
    status = factory.Iterator([SessionStatus.BUSY, SessionStatus.IDLE])
    tools = factory.List([])
    todos = factory.SubFactory(AgentTodosFactory)
    parent_id = None
    has_pending_ask_user = False
    ask_user_title = ""
    ask_user_question = ""
    ask_user_options = factory.List([])
    ask_user_repo = ""
    ask_user_agent = ""
    ask_user_branch = ""
    ask_user_urgency = "normal"


class InstanceFactory(factory.Factory):
    class Meta:
        model = Instance

    port = factory.Sequence(lambda n: 3000 + n)
    agents = factory.List([])


class SessionDataFactory(factory.DictFactory):
    session_id = factory.Faker("uuid4")
    project_path = factory.Faker("file_path", depth=3)
    created_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    updated_at = factory.LazyFunction(lambda: datetime.now().isoformat())
    status = "active"


class MessageDataFactory(factory.DictFactory):
    message_id = factory.Faker("uuid4")
    session_id = factory.Faker("uuid4")
    role = factory.Iterator(["user", "assistant"])
    content = factory.Faker("paragraph")
    timestamp = factory.LazyFunction(lambda: datetime.now().isoformat())
    tokens_input = factory.Faker("random_int", min=10, max=1000)
    tokens_output = factory.Faker("random_int", min=10, max=1000)
