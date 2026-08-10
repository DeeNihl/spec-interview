"""Provider-neutral speech output boundaries."""

from spec_interview.speech.provider import SpeechProvider
from spec_interview.speech.termux import TermuxSpeechProvider, sentence_chunks

__all__ = ["SpeechProvider", "TermuxSpeechProvider", "sentence_chunks"]
