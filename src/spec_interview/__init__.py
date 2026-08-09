"""Provider-neutral runtime for technical specification interviews."""

from spec_interview.conversation.manager import ConversationManager
from spec_interview.conversation.provider import ConversationProvider

__all__ = ["ConversationManager", "ConversationProvider"]
__version__ = "0.1.0"
