import os
import yaml
from pydantic import BaseModel, Field  # type: ignore
from typing import Dict, Any, List, Optional


class LLMConfig(BaseModel):
    """Configuration for LLM providers"""

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    xai_api_key: Optional[str] = Field(default=None, alias="XAI_API_KEY")
    perplexity_api_key: Optional[str] = Field(default=None, alias="PERPLEXITY_API_KEY")
    cerebras_api_key: Optional[str] = Field(default=None, alias="CEREBRAS_API_KEY")
    sambanova_api_key: Optional[str] = Field(default=None, alias="SAMBANOVA_API_KEY")
    fireworks_api_key: Optional[str] = Field(default=None, alias="FIREWORKS_API_KEY")
    deepinfra_api_key: Optional[str] = Field(default=None, alias="DEEPINFRA_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    mistral_api_key: Optional[str] = Field(default=None, alias="MISTRAL_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")


class SecurityConfig(BaseModel):
    """Security-related configuration"""

    megabot_backup_key: Optional[str] = Field(default=None, alias="MEGABOT_BACKUP_KEY")
    megabot_encryption_salt: str = Field(
        default="megabot-static-salt", alias="MEGABOT_ENCRYPTION_SALT"
    )
    megabot_media_path: str = Field(default="./media", alias="MEGABOT_MEDIA_PATH")


class AdapterConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3000
    bridge_type: str = "websocket"
    database_url: str = "sqlite:///megabot.db"
    vector_db: str = "pgvector"
    servers: list[dict] = []
    web_search: Dict[str, Any] = {}
    auth_token: str = ""  # From environment variable
    encryption_key: str = ""  # For WebSocket encryption


class SystemConfig(BaseModel):
    name: str = "MegaBot"
    local_only: bool = True
    bind_address: str = "127.0.0.1"
    telemetry: bool = False
    default_mode: str = "plan"
    admin_phone: Optional[str] = None
    dnd_start: int = 22  # 10 PM
    dnd_end: int = 7  # 7 AM


class Config(BaseModel):
    system: SystemConfig
    adapters: Dict[str, AdapterConfig]
    paths: Dict[str, str]
    policies: Dict[str, Any] = {"allow": [], "deny": []}
    admins: List[str] = []  # List of authorized sender IDs (e.g. your phone number)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    def validate_environment(self):
        """Ensure required environment variables are present"""
        required_env_vars = {
            "OPENCLAW_AUTH_TOKEN": "Required for OpenClaw adapter authentication",
        }

        # Add provider specific requirements if configured
        if "openai" in self.adapters:
            required_env_vars["OPENAI_API_KEY"] = "Required for OpenAI LLM provider"
        if "anthropic" in self.adapters:
            required_env_vars["ANTHROPIC_API_KEY"] = (
                "Required for Anthropic LLM provider"
            )

        missing = []
        for var, description in required_env_vars.items():
            if not os.environ.get(var) and not (
                self.adapters.get("openclaw") and self.adapters["openclaw"].auth_token
            ):
                # Specific check for openclaw auth_token in config vs env
                if (
                    var == "OPENCLAW_AUTH_TOKEN"
                    and self.adapters.get("openclaw")
                    and self.adapters["openclaw"].auth_token
                ):
                    continue
                missing.append(f"{var}: {description}")

        if missing:
            error_msg = "\n".join(missing)
            print(
                f"❌ Configuration Error: Missing required environment variables:\n{error_msg}"
            )
            # In production we might raise SystemExit, but for now we warn
            return False
        return True

    def save(self, path: str = "mega-config.yaml"):
        """Save current configuration back to disk"""
        with open(path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)


def load_config(path: str = "mega-config.yaml") -> Config:
    # Check if config file exists, create default if not
    if not os.path.exists(path):
        print(f"⚠️  Config file {path} not found, creating default configuration...")
        default_config = Config(
            system=SystemConfig(),
            adapters={},
            paths={"workspaces": os.getcwd(), "external_repos": os.getcwd()},
            llm=LLMConfig(),
            security=SecurityConfig(),
        )
        # Auto-populate from environment
        _populate_from_environment(default_config)
        default_config.save(path)
        return default_config

    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    config = Config(**data)

    # Auto-inject environment variables into adapter configs if empty
    if "openclaw" in config.adapters and not config.adapters["openclaw"].auth_token:
        config.adapters["openclaw"].auth_token = os.environ.get(
            "OPENCLAW_AUTH_TOKEN", ""
        )

    # Populate LLM and security configs from environment
    _populate_from_environment(config)

    return config


def _populate_from_environment(config: Config) -> None:
    """Populate configuration from environment variables"""
    # LLM API Keys
    env_mappings = {
        "llm.openai_api_key": "OPENAI_API_KEY",
        "llm.groq_api_key": "GROQ_API_KEY",
        "llm.deepseek_api_key": "DEEPSEEK_API_KEY",
        "llm.xai_api_key": "XAI_API_KEY",
        "llm.perplexity_api_key": "PERPLEXITY_API_KEY",
        "llm.cerebras_api_key": "CEREBRAS_API_KEY",
        "llm.sambanova_api_key": "SAMBANOVA_API_KEY",
        "llm.fireworks_api_key": "FIREWORKS_API_KEY",
        "llm.deepinfra_api_key": "DEEPINFRA_API_KEY",
        "llm.anthropic_api_key": "ANTHROPIC_API_KEY",
        "llm.gemini_api_key": "GEMINI_API_KEY",
        "llm.mistral_api_key": "MISTRAL_API_KEY",
        "llm.openrouter_api_key": "OPENROUTER_API_KEY",
        "llm.github_token": "GITHUB_TOKEN",
        "security.megabot_backup_key": "MEGABOT_BACKUP_KEY",
        "security.megabot_encryption_salt": "MEGABOT_ENCRYPTION_SALT",
        "security.megabot_media_path": "MEGABOT_MEDIA_PATH",
    }

    for config_path, env_var in env_mappings.items():
        if os.environ.get(env_var):
            _set_nested_attr(config, config_path, os.environ[env_var])


def _set_nested_attr(obj: Any, path: str, value: Any) -> None:
    """Set a nested attribute on an object using dot notation"""
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if not hasattr(current, part):
            return
        current = getattr(current, part)
    if hasattr(current, parts[-1]):
        setattr(current, parts[-1], value)
