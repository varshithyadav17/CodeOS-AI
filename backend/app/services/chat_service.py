"""Chat service — wraps Gemini 2.5 Pro via the standalone google-genai SDK."""
from __future__ import annotations
import logging
from ..llm.chat_compat import LlmChat, UserMessage

from ..core.config import settings
from ..core.interfaces.metadata import IMetadataRepository
from ..core.models.conversation import Conversation, Message
from .retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CodeOS AI, an expert software engineering assistant operating over a user's code repository.

Rules:
- Answer questions strictly from the provided code context.
- Reference exact file paths and line ranges in your answers.
- When asked about architecture, describe components, their relationships, and data flow.
- When unsure, say so and suggest where to look in the repo.
- Prefer concise, structured answers with bullet points and short code excerpts.
- Use Markdown. Use fenced code blocks for code."""


class ChatService:
    def __init__(
        self,
        conversations: IMetadataRepository[Conversation],
        messages: IMetadataRepository[Message],
        retrieval: RetrievalService,
    ):
        self.conversations = conversations
        self.messages = messages
        self.retrieval = retrieval

    async def ensure_conversation(self, repo_id: str, user_id: str, conversation_id: str | None, first_text: str) -> Conversation:
        if conversation_id:
            conv = await self.conversations.get(conversation_id)
            if conv:
                return conv
        title = (first_text[:60] + "…") if len(first_text) > 60 else first_text
        conv = Conversation(repo_id=repo_id, user_id=user_id, title=title or "New chat")
        await self.conversations.insert(conv)
        return conv

    async def get_messages(self, conversation_id: str) -> list[Message]:
        return await self.messages.list({"conversation_id": conversation_id}, limit=200, sort=[("created_at", 1)])

    async def ask(self, repo_id: str, user_id: str, conversation_id: str | None, question: str) -> dict:
        conv = await self.ensure_conversation(repo_id, user_id, conversation_id, question)
        # Persist user message
        user_msg = Message(conversation_id=conv.id, role="user", content=question)
        await self.messages.insert(user_msg)

        # Retrieve hybrid context
        chunks, nodes = await self.retrieval.hybrid(repo_id, question, k=6)
        context = self.retrieval.format_context(chunks, nodes)
        context_node_ids = [n.id for n in nodes] + [c.node_id for c in chunks if c.node_id]

        # Past messages for short-term memory
        history = await self.get_messages(conv.id)
        history_text = "\n".join(
            f"{m.role.upper()}: {m.content[:600]}" for m in history[-6:] if m.id != user_msg.id
        )

        prompt = f"""{history_text}

# Repository Context
{context if context else '(no indexed code yet for this repo — answer generally and ask the user to check ingestion status)'}

# Question
{question}
"""

        chat = LlmChat(
            api_key=settings.GEMINI_API_KEY,
            session_id=f"repo-{repo_id}-conv-{conv.id}",
            system_message=SYSTEM_PROMPT,
        ).with_model("gemini", settings.LLM_MODEL)

        try:
            answer_obj = await chat.send_message(UserMessage(text=prompt))
            answer = answer_obj if isinstance(answer_obj, str) else getattr(answer_obj, "content", str(answer_obj))
        except Exception as e:
            logger.exception("LLM error")
            answer = f"Sorry, the LLM call failed: {e}"

        assistant_msg = Message(conversation_id=conv.id, role="assistant", content=answer, context_nodes=context_node_ids)
        await self.messages.insert(assistant_msg)
        await self.conversations.update(conv.id, {})

        return {
            "conversation_id": conv.id,
            "message": assistant_msg.model_dump(),
            "context": [n.model_dump() for n in nodes][:15],
        }
