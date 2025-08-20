# In backend/core/insights.py

import os
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import json

# LangChain is used as an abstraction layer to interact with various LLM providers.
# This makes it easy to switch between models like Gemini, OpenAI, etc.
try:
    from langchain_openai import ChatOpenAI, AzureChatOpenAI
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_community.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
except ImportError as e:
    raise ImportError(
        "Required LangChain packages not found. Please install:\n"
        "pip install langchain langchain-openai langchain-google-genai langchain-community"
    ) from e

# Configure logging (removed, now configured globally in main.py)
logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    AZURE = "azure"
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""
    provider: LLMProvider
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 30

    # Provider-specific configs
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    deployment_name: Optional[str] = None
    credentials_path: Optional[str] = None


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class ConfigurationError(LLMError):
    """Raised when LLM configuration is invalid."""
    pass


class ProviderError(LLMError):
    """Raised when LLM provider call fails."""
    pass


class LLMManager:
    """
    Unified LLM interface supporting multiple providers with improved error handling,
    configuration management, and extensibility.
    """

    DEFAULT_MODELS = {
        LLMProvider.GEMINI: "gemini-2.5-flash",
        LLMProvider.AZURE: "gpt-4o",
        LLMProvider.OPENAI: "gpt-4o",
        LLMProvider.OLLAMA: "llama3",
    }

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM Manager with configuration."""
        if config:
            self.config = config
        else:
            self.config = self._load_config_from_env()

        logger.debug(f"DEBUG: LLMManager: Initializing with config: {self.config}")
        try:
            self._validate_config()
            self.llm = self._initialize_llm()
            logger.debug(f"DEBUG: LLMManager: LLM initialized successfully for provider: {self.config.provider.value}")
        except Exception as e:
            logger.critical(f"CRITICAL: LLMManager: Initialization failed: {e}")
            raise # Re-raise the exception to propagate it

    @classmethod
    def from_env(cls, provider: Optional[str] = None) -> "LLMManager":
        """Create LLMManager from environment variables."""
        logger.debug(f"DEBUG: LLMManager: Creating from environment with provider override: {provider}")
        return cls(cls._load_config_from_env(provider))

    @classmethod
    def _load_config_from_env(cls, provider: Optional[str] = None) -> LLMConfig:
        """Load configuration from environment variables."""
        provider_str = provider or os.getenv("LLM_PROVIDER", "gemini")
        logger.debug(f"DEBUG: LLMManager: Loading config from env. LLM_PROVIDER: '{provider_str}'")

        try:
            provider_enum = LLMProvider(provider_str.lower())
            logger.debug(f"DEBUG: LLMManager: Resolved LLMProvider enum: {provider_enum.value}")
        except ValueError as e:
            valid_providers = [p.value for p in LLMProvider]
            logger.error(f"ERROR: LLMManager: Invalid LLM_PROVIDER: '{provider_str}'. Valid options: {valid_providers}. Error: {e}")
            raise ConfigurationError(
                f"Invalid LLM_PROVIDER: {provider_str}. "
                f"Valid options: {valid_providers}"
            ) from e

        temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        max_tokens = os.getenv("LLM_MAX_TOKENS")
        max_tokens = int(max_tokens) if max_tokens else None
        timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        logger.debug(f"DEBUG: LLMManager: Common config - Temp: {temperature}, Max Tokens: {max_tokens}, Timeout: {timeout}")

        if provider_enum == LLMProvider.GEMINI:
            api_key = os.getenv("GOOGLE_API_KEY")
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            logger.debug(f"DEBUG: LLMManager: Gemini env vars - GOOGLE_API_KEY: {bool(api_key)}, GOOGLE_APPLICATION_CREDENTIALS: {bool(credentials_path)}")
            config = LLMConfig(
                provider=provider_enum,
                model=os.getenv("GEMINI_MODEL", cls.DEFAULT_MODELS[provider_enum]),
                temperature=temperature, max_tokens=max_tokens, timeout=timeout,
                api_key=api_key,
                credentials_path=credentials_path
            )
            logger.debug(f"DEBUG: LLMManager: Gemini config loaded. Model: {config.model}, API Key present: {bool(config.api_key)}, Credentials Path present: {bool(config.credentials_path)}")
            return config
        elif provider_enum == LLMProvider.AZURE:
            api_key = os.getenv("AZURE_OPENAI_KEY")
            api_base = os.getenv("AZURE_OPENAI_BASE")
            api_version = os.getenv("AZURE_API_VERSION")
            deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME", cls.DEFAULT_MODELS[provider_enum])
            logger.debug(f"DEBUG: LLMManager: Azure env vars - AZURE_OPENAI_KEY: {bool(api_key)}, AZURE_OPENAI_BASE: {bool(api_base)}, AZURE_API_VERSION: {bool(api_version)}, AZURE_DEPLOYMENT_NAME: {bool(deployment_name)}")
            config = LLMConfig(
                provider=provider_enum,
                model=deployment_name, # Use deployment_name as model for Azure
                temperature=temperature, max_tokens=max_tokens, timeout=timeout,
                api_key=api_key,
                api_base=api_base,
                api_version=api_version,
                deployment_name=deployment_name
            )
            logger.debug(f"DEBUG: LLMManager: Azure config loaded. Deployment: {config.deployment_name}, API Key present: {bool(config.api_key)}")
            return config
        elif provider_enum == LLMProvider.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
            api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            logger.debug(f"DEBUG: LLMManager: OpenAI env vars - OPENAI_API_KEY: {bool(api_key)}, OPENAI_API_BASE: {bool(api_base)}")
            config = LLMConfig(
                provider=provider_enum,
                model=os.getenv("OPENAI_MODEL", cls.DEFAULT_MODELS[provider_enum]),
                temperature=temperature, max_tokens=max_tokens, timeout=timeout,
                api_key=api_key,
                api_base=api_base
            )
            logger.debug(f"DEBUG: LLMManager: OpenAI config loaded. Model: {config.model}, API Key present: {bool(config.api_key)}")
            return config
        elif provider_enum == LLMProvider.OLLAMA:
            api_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            logger.debug(f"DEBUG: LLMManager: Ollama env vars - OLLAMA_BASE_URL: {bool(api_base)}")
            config = LLMConfig(
                provider=provider_enum,
                model=os.getenv("OLLAMA_MODEL", cls.DEFAULT_MODELS[provider_enum]),
                temperature=temperature, max_tokens=max_tokens, timeout=timeout,
                api_base=api_base
            )
            logger.debug(f"DEBUG: LLMManager: Ollama config loaded. Model: {config.model}, Base URL: {config.api_base}")
            return config
        else:
            logger.error(f"ERROR: LLMManager: Provider {provider_enum} not yet implemented in _load_config_from_env.")
            raise ConfigurationError(f"Provider {provider_enum} not yet implemented")

    def _validate_config(self) -> None:
        """Validate the current configuration."""
        logger.debug(f"DEBUG: LLMManager: Validating config for provider: {self.config.provider.value}")
        if self.config.provider == LLMProvider.GEMINI:
            if not (self.config.api_key or self.config.credentials_path):
                error_msg = "Gemini requires either GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS."
                logger.error(f"ERROR: LLMManager: {error_msg}")
                raise ConfigurationError(error_msg)
        elif self.config.provider == LLMProvider.AZURE:
            missing = [var for var in ["api_key", "api_base", "api_version", "deployment_name"] if not getattr(self.config, var)]
            if missing: 
                error_msg = f"Missing required Azure config: {missing}"
                logger.error(f"ERROR: LLMManager: {error_msg}")
                raise ConfigurationError(error_msg)
        elif self.config.provider == LLMProvider.OPENAI:
            if not self.config.api_key: 
                error_msg = "OpenAI requires OPENAI_API_KEY."
                logger.error(f"ERROR: LLMManager: {error_msg}")
                raise ConfigurationError(error_msg)
        elif self.config.provider == LLMProvider.OLLAMA:
            if not self.config.api_base:
                error_msg = "Ollama requires OLLAMA_BASE_URL."
                logger.error(f"ERROR: LLMManager: {error_msg}")
                raise ConfigurationError(error_msg)
        logger.debug(f"DEBUG: LLMManager: Config validation successful for provider: {self.config.provider.value}")

    def _initialize_llm(self):
        """Initialize the appropriate LLM client."""
        logger.debug(f"DEBUG: LLMManager: Initializing LLM client for provider: {self.config.provider.value}")
        try:
            if self.config.provider == LLMProvider.GEMINI:
                llm_client = ChatGoogleGenerativeAI(model=self.config.model, temperature=self.config.temperature, google_api_key=self.config.api_key)
                logger.debug(f"DEBUG: LLMManager: Initialized ChatGoogleGenerativeAI with model: {self.config.model}")
                return llm_client
            elif self.config.provider == LLMProvider.AZURE:
                llm_client = AzureChatOpenAI(azure_deployment=self.config.deployment_name, openai_api_version=self.config.api_version, azure_endpoint=self.config.api_base, api_key=self.config.api_key, temperature=self.config.temperature)
                logger.debug(f"DEBUG: LLMManager: Initialized AzureChatOpenAI with deployment: {self.config.deployment_name}")
                return llm_client
            elif self.config.provider == LLMProvider.OPENAI:
                llm_client = ChatOpenAI(model=self.config.model, api_key=self.config.api_key, base_url=self.config.api_base, temperature=self.config.temperature)
                logger.debug(f"DEBUG: LLMManager: Initialized ChatOpenAI with model: {self.config.model}")
                return llm_client
            elif self.config.provider == LLMProvider.OLLAMA:
                llm_client = ChatOllama(model=self.config.model, base_url=self.config.api_base, temperature=self.config.temperature)
                logger.debug(f"DEBUG: LLMManager: Initialized ChatOllama with model: {self.config.model}")
                return llm_client
            else:
                logger.error(f"ERROR: LLMManager: Provider {self.config.provider} not implemented in _initialize_llm.")
                raise ConfigurationError(f"Provider {self.config.provider} not implemented")
        except Exception as e:
            logger.critical(f"CRITICAL: LLMManager: Failed to initialize {self.config.provider.value} LLM: {e}")
            raise ConfigurationError(f"Failed to initialize {self.config.provider.value} LLM: {e}")

    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Union[HumanMessage, SystemMessage, AIMessage]]:
        """Convert message dictionaries to LangChain message objects."""
        formatted_messages = []
        for msg in messages:
            role, content = msg.get("role", "").lower(), msg.get("content", "")
            if role == "system": formatted_messages.append(SystemMessage(content=content))
            elif role in ("user", "human"): formatted_messages.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"): formatted_messages.append(AIMessage(content=content))
            else: logger.warning(f"WARNING: LLMManager: Unknown message role: {role}, treating as human."); formatted_messages.append(HumanMessage(content=content))
        logger.debug(f"DEBUG: LLMManager: Formatted {len(messages)} messages into LangChain format.")
        return formatted_messages

    def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get response from the configured LLM."""
        logger.debug(f"DEBUG: LLMManager: Attempting to get response from {self.config.provider.value} LLM.")
        try:
            formatted_messages = self._format_messages(messages)
            logger.info(f"INFO: LLMManager: Calling {self.config.provider.value} with {len(messages)} messages. First message content: '{messages[0]['content'][:50]}...'")
            response = self.llm.invoke(formatted_messages)
            logger.info(f"INFO: LLMManager: Received response from {self.config.provider.value}. Content length: {len(response.content)}")
            return response.content
        except Exception as e:
            error_msg = f"{self.config.provider.value} call failed: {str(e)}"
            logger.error(f"ERROR: LLMManager: {error_msg}")
            raise ProviderError(error_msg) from e

    def get_responses_batch(self, list_of_message_lists: List[List[Dict[str, str]]]) -> List[str]:
        """Get responses for a batch of message lists from the configured LLM."""
        logger.debug(f"DEBUG: LLMManager: Attempting to get batch responses from {self.config.provider.value} LLM for {len(list_of_message_lists)} requests.")
        try:
            formatted_batches = [self._format_messages(messages) for messages in list_of_message_lists]
            logger.info(f"INFO: LLMManager: Calling {self.config.provider.value} for a batch of {len(list_of_message_lists)} requests.")
            
            # LangChain's batch method for chat models
            responses = self.llm.batch(formatted_batches)
            
            result_contents = [res.content for res in responses]
            logger.info(f"INFO: LLMManager: Received batch responses from {self.config.provider.value}. Total responses: {len(result_contents)}")
            return result_contents
        except Exception as e:
            error_msg = f"{self.config.provider.value} batch call failed: {str(e)}"
            logger.error(f"ERROR: LLMManager: {error_msg}")
            raise ProviderError(error_msg) from e

def get_llm_response(messages: List[Dict[str, str]], provider: Optional[str] = None) -> str:
    """
    A simple, backward-compatible function to get a response from the LLM.
    """
    logger.debug(f"DEBUG: get_llm_response: Creating LLMManager instance.")
    manager = LLMManager.from_env(provider)
    logger.debug(f"DEBUG: get_llm_response: Calling manager.get_response.")
    return manager.get_response(messages)

def get_llm_response_two_sentences(messages: List[Dict[str, str]], provider: Optional[str] = None) -> str:
    """
    A simple function to get a two-sentence response from the LLM.
    """
    logger.debug(f"DEBUG: get_llm_response_two_sentences: Creating LLMManager instance.")
    manager = LLMManager.from_env(provider)
    logger.debug(f"DEBUG: get_llm_response_two_sentences: Calling manager.get_response.")
    
    # Prepend a system message to ensure a two-sentence response
    system_message = {"role": "system", "content": "Summarize the following content in exactly two concise sentences."}
    
    # Ensure the original messages are not modified, and prepend the system message
    modified_messages = [system_message] + messages
    
    return manager.get_response(modified_messages)

def get_llm_response_json(messages: List[Dict[str, str]], response_model: Any, provider: Optional[str] = None) -> Any:
    """
    A function to get a JSON response from the LLM, parsed into a Pydantic model.
    """
    logger.debug(f"DEBUG: get_llm_response_json: Creating LLMManager instance.")
    manager = LLMManager.from_env(provider)
    logger.debug(f"DEBUG: get_llm_response_json: Calling manager.get_response.")

    # Add a system message to ensure JSON output
    system_message = {
        "role": "system",
        "content": f"Your response MUST be a JSON object that conforms to the following Pydantic schema:\n\n{response_model.schema_json(indent=2)}\n\nDo NOT include any other text or explanations outside the JSON object."
    }
    
    modified_messages = [system_message] + messages
    
    json_string = manager.get_response(modified_messages)
    
    # Attempt to strip markdown code block delimiters if present
    if json_string.startswith("```json") and json_string.endswith("```"):
        json_string = json_string.lstrip("```json").rstrip("```").strip()
    elif json_string.startswith("```") and json_string.endswith("```"):
        json_string = json_string.lstrip("```").rstrip("```").strip()

    try:
        # Attempt to parse the JSON string into the Pydantic model
        return response_model.parse_raw(json_string)
    except Exception as e:
        logger.error(f"ERROR: get_llm_response_json: Failed to parse LLM response into Pydantic model: {e}. Raw response: {json_string[:500]}...")
        raise ValueError(f"LLM response did not conform to the expected JSON schema: {e}") from e
