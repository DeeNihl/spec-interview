"""Single provider construction point."""

from __future__ import annotations

from spec_interview.config.models import AppConfig, ProviderName
from spec_interview.conversation.provider import ConversationProvider
from spec_interview.providers.gemma import LocalGemmaProvider, OpenAICompatibleGemmaTransport
from spec_interview.providers.mock import MockConversationProvider
from spec_interview.providers.nova import BedrockNovaSonicProvider
from spec_interview.providers.parlor import LocalParlorGemmaProvider


class ConversationProviderFactory:
    @staticmethod
    def create(name: ProviderName, config: AppConfig) -> ConversationProvider:
        if name == "mock":
            return MockConversationProvider()
        if name == "gemma-local":
            transport = OpenAICompatibleGemmaTransport(
                config.gemma_endpoint,
                api_key=config.gemma_api_key,
            )
            return LocalGemmaProvider(model=config.gemma_model, transport=transport)
        if name == "parlor-gemma":
            return LocalParlorGemmaProvider(config.parlor_endpoint)
        if name == "nova-sonic":
            return BedrockNovaSonicProvider(region=config.aws_region)
        raise ValueError(f"unknown provider: {name}")

    @staticmethod
    def names() -> tuple[ProviderName, ...]:
        return ("mock", "gemma-local", "parlor-gemma", "nova-sonic")
