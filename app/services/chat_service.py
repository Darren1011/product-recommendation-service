from datetime import UTC, datetime
from uuid import uuid4

from app.models import ChatMessage, ChatThreadDetail, ChatThreadSummary


# Keep thread state in process memory for the prototype.
class ChatService:
    """In-memory chat history store used by the prototype UI."""

    def __init__(self) -> None:
        """Create empty thread state for the running process."""
        # Store thread metadata separately from messages for simpler list views.
        self.thread_meta: dict[str, dict[str, str | bool]] = {}
        self.messages_by_thread: dict[str, list[ChatMessage]] = {}

    def add_exchange(
        self,
        chat_id: str | None,
        user_text: str,
        assistant_text: str,
        workflow_id: str | None,
    ) -> tuple[str, str, str]:
        """Append a user and assistant message to a chat thread."""
        # Reuse an existing thread or create a new one for first message.
        thread_id = chat_id or str(uuid4())
        self._ensure_thread(thread_id, user_text)

        # Store the user message before the assistant response.
        self._append_message(thread_id, "user", user_text, None)
        assistant_message = self._append_message(
            thread_id,
            "assistant",
            assistant_text,
            workflow_id,
        )
        self.thread_meta[thread_id]["updated_at"] = _utc_now()
        return thread_id, assistant_message.id, str(self.thread_meta[thread_id]["name"])

    def list_threads(self) -> list[ChatThreadSummary]:
        """Return all chat threads ordered by latest activity."""
        # Build summaries from metadata and latest message.
        summaries = [
            self._build_summary(thread_id)
            for thread_id in self.messages_by_thread
        ]
        return sorted(summaries, key=lambda thread: thread.updated_at, reverse=True)

    def get_thread(self, chat_id: str) -> ChatThreadDetail | None:
        """Return one full chat thread."""
        # Missing ids are handled by the API layer as 404s.
        if chat_id not in self.messages_by_thread:
            return None
        return self._build_detail(chat_id)

    def rename_thread(self, chat_id: str, name: str) -> ChatThreadDetail | None:
        """Rename a chat thread."""
        # Validate thread existence before changing metadata.
        if chat_id not in self.thread_meta:
            return None
        self.thread_meta[chat_id]["name"] = name
        self.thread_meta[chat_id]["updated_at"] = _utc_now()
        return self._build_detail(chat_id)

    def set_favorite(self, chat_id: str, is_favorite: bool) -> ChatThreadDetail | None:
        """Update the favorite flag for a chat thread."""
        # Validate thread existence before changing metadata.
        if chat_id not in self.thread_meta:
            return None
        self.thread_meta[chat_id]["is_favorite"] = is_favorite
        self.thread_meta[chat_id]["updated_at"] = _utc_now()
        return self._build_detail(chat_id)

    def _ensure_thread(self, thread_id: str, user_text: str) -> None:
        # Initialize thread metadata with a simple local title.
        if thread_id in self.thread_meta:
            return
        self.thread_meta[thread_id] = {
            "name": _build_chat_name(user_text),
            "updated_at": _utc_now(),
            "is_favorite": False,
        }
        self.messages_by_thread[thread_id] = []

    def _append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        workflow_id: str | None,
    ) -> ChatMessage:
        # Create a serializable chat message for the frontend.
        message = ChatMessage(
            id=str(uuid4()),
            role=role,
            content=content,
            created_at=_utc_now(),
            workflow_id=workflow_id,
        )
        self.messages_by_thread[thread_id].append(message)
        return message

    def _build_summary(self, thread_id: str) -> ChatThreadSummary:
        # Derive the latest message for sidebar previews.
        meta = self.thread_meta[thread_id]
        messages = self.messages_by_thread[thread_id]
        latest_message = messages[-1].content if messages else ""
        return ChatThreadSummary(
            id=thread_id,
            name=str(meta["name"]),
            updated_at=str(meta["updated_at"]),
            is_favorite=bool(meta["is_favorite"]),
            message_count=len(messages),
            latest_message=latest_message,
        )

    def _build_detail(self, thread_id: str) -> ChatThreadDetail:
        # Return all messages for a selected thread.
        meta = self.thread_meta[thread_id]
        return ChatThreadDetail(
            id=thread_id,
            name=str(meta["name"]),
            updated_at=str(meta["updated_at"]),
            is_favorite=bool(meta["is_favorite"]),
            messages=self.messages_by_thread[thread_id],
        )


# Create compact timestamps that remain easy to inspect in JSON responses.
def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


# Create a chat name locally without calling an LLM or external service.
def _build_chat_name(user_text: str) -> str:
    clean_text = " ".join(user_text.split())
    if not clean_text:
        return "New Chat"
    if len(clean_text) <= 100:
        return clean_text
    return "New Chat"
