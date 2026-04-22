# tests/test_llm_client.py
import pytest
from unittest.mock import patch, MagicMock
from memex.llm_client import LLMClient, LLMResponse


def test_llm_response_has_text():
    r = LLMResponse(text="hello")
    assert r.text == "hello"


def test_anthropic_client_calls_messages_api():
    client = LLMClient(provider="anthropic", model="claude-haiku-4-5-20251001", base_url=None)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="result text")]

    with patch("memex.llm_client.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response
        result = client.complete(prompt="test prompt", max_tokens=100)

    assert result.text == "result text"
    mock_anthropic.Anthropic.return_value.messages.create.assert_called_once()
    call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["max_tokens"] == 100
    assert call_kwargs["messages"][0]["content"] == "test prompt"


def test_openai_compatible_client_calls_chat_api():
    client = LLMClient(provider="openai", model="gpt-4o-mini", base_url="http://localhost:11434")
    mock_choice = MagicMock()
    mock_choice.message.content = "openai result"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("memex.llm_client.openai") as mock_openai:
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_response
        result = client.complete(prompt="test prompt", max_tokens=200)

    assert result.text == "openai result"
    mock_openai.OpenAI.assert_called_once_with(base_url="http://localhost:11434", api_key="ollama")


def test_unknown_provider_raises():
    client = LLMClient(provider="unknown", model="x", base_url=None)
    with pytest.raises(ValueError, match="Unknown provider"):
        client.complete(prompt="hi", max_tokens=10)
