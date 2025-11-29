"""
Companion BaaS Configuration Management
Centralized configuration for all brain components
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class ElasticsearchConfig:
    """Elasticsearch vector database configuration"""
    host: str = os.getenv('ES_HOST', 'localhost')
    port: int = int(os.getenv('ES_PORT', 9200))
    index_name: str = 'companion_knowledge'
    embedding_model: str = 'sentence-transformers/all-MiniLM-L6-v2'
    vector_dim: int = 384
    max_results: int = 10
    enabled: bool = False  # Disabled by default to avoid connection delays


@dataclass
class MeilisearchConfig:
    """Meilisearch full-text search configuration"""
    host: str = os.getenv('MEILI_HOST', 'localhost')
    port: int = int(os.getenv('MEILI_PORT', 7700))
    master_key: str = os.getenv('MEILI_MASTER_KEY', 'masterKey123')
    index_name: str = 'conversations'
    searchable_fields: List[str] = field(default_factory=lambda: ['message', 'response', 'metadata'])
    filterable_fields: List[str] = field(default_factory=lambda: ['user_id', 'app_type', 'timestamp'])
    sortable_fields: List[str] = field(default_factory=lambda: ['timestamp', 'relevance_score'])
    enabled: bool = True


@dataclass
class Crawl4AIConfig:
    """Crawl4AI web scraping configuration"""
    docker_host: str = os.getenv('CRAWL4AI_HOST', 'localhost:8000')
    headless: bool = True
    timeout: int = 30
    max_pages: int = 10
    output_format: str = 'markdown'
    js_enabled: bool = True
    extract_images: bool = False
    enabled: bool = True


@dataclass
class BytezConfig:
    """Bytez API configuration"""
    api_key: str = os.getenv('BYTEZ_API_KEY', '6013ed61509ab6ba3c2fa9252e8e5fa2')
    base_url: str = 'https://api.bytez.com/v1'
    default_model: str = 'phi-2'  # Fast 2.7B model
    max_tokens: int = 2048
    temperature: float = 0.7
    enabled: bool = True  # Free tier available!


@dataclass
class BrowserUseConfig:
    """Browser-Use automation configuration"""
    headless: bool = True
    timeout: int = 60
    max_steps: int = 20
    screenshot_on_error: bool = True
    proxy: Optional[str] = None
    enabled: bool = False  # Resource intensive, disabled by default


@dataclass
class PublicAPIsConfig:
    """Public APIs integration configuration"""
    enabled_categories: List[str] = field(default_factory=lambda: [
        'weather', 'news', 'finance', 'cryptocurrency',
        'animals', 'books', 'music', 'sports'
    ])
    cache_ttl: int = 300  # 5 minutes
    max_retries: int = 3
    timeout: int = 10
    enabled: bool = True


@dataclass
class CodeExecutionConfig:
    """Open Interpreter code execution configuration"""
    enabled: bool = True
    sandboxed: bool = True
    allowed_languages: List[str] = field(default_factory=lambda: ['python', 'javascript', 'bash'])
    max_execution_time: int = 30
    max_memory_mb: int = 512
    allow_network: bool = False
    allow_file_write: bool = False


@dataclass
class StableDiffusionConfig:
    """Stable Diffusion image generation configuration"""
    model: str = 'stabilityai/stable-diffusion-2-1'
    device: str = 'cpu'  # Will auto-detect GPU
    num_inference_steps: int = 50
    guidance_scale: float = 7.5
    image_size: tuple = (512, 512)
    save_path: str = 'generated_images/'
    enabled: bool = False  # GPU intensive, disabled by default


@dataclass
class RedisConfig:
    """Redis caching configuration"""
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', 6379))
    db: int = 0
    password: Optional[str] = os.getenv('REDIS_PASSWORD')
    cache_ttl: int = 3600  # 1 hour default
    max_memory: str = '256mb'
    enabled: bool = True


@dataclass
class BytezConfig:
    """Bytez API configuration - 141k+ small models"""
    api_key: str = os.getenv('BYTEZ_API_KEY', '6013ed61509ab6ba3c2fa9252e8e5fa2')
    enabled: bool = True
    default_model: str = 'Qwen/Qwen3-4B-Instruct-2507'
    concurrent_requests: int = 1  # Free tier limit
    # Recommended models by task
    models: Dict[str, str] = field(default_factory=lambda: {
        'chat': 'Qwen/Qwen3-4B-Instruct-2507',
        'code': 'deepseek-ai/deepseek-coder-1.3b-instruct',
        'reasoning': 'microsoft/phi-2',
        'general': 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'
    })


@dataclass
class BrainConfig:
    """Master brain configuration"""
    # Core settings
    debug: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # Component configs
    bytez: BytezConfig = field(default_factory=BytezConfig)
    elasticsearch: ElasticsearchConfig = field(default_factory=ElasticsearchConfig)
    meilisearch: MeilisearchConfig = field(default_factory=MeilisearchConfig)
    crawl4ai: Crawl4AIConfig = field(default_factory=Crawl4AIConfig)
    browser_use: BrowserUseConfig = field(default_factory=BrowserUseConfig)
    public_apis: PublicAPIsConfig = field(default_factory=PublicAPIsConfig)
    code_execution: CodeExecutionConfig = field(default_factory=CodeExecutionConfig)
    stable_diffusion: StableDiffusionConfig = field(default_factory=StableDiffusionConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    
    # Resource limits
    max_workers: int = 4
    max_memory_mb: int = 2048
    max_cpu_percent: float = 80.0
    
    # Paths
    base_path: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    cache_path: Path = field(default_factory=lambda: Path(__file__).parent.parent / 'cache')
    logs_path: Path = field(default_factory=lambda: Path(__file__).parent.parent / 'logs')
    
    def __post_init__(self):
        """Create necessary directories"""
        self.cache_path.mkdir(exist_ok=True)
        self.logs_path.mkdir(exist_ok=True)
        if self.stable_diffusion.enabled:
            Path(self.stable_diffusion.save_path).mkdir(exist_ok=True)


# Global configuration instance
_config: Optional[BrainConfig] = None


def get_config() -> BrainConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = BrainConfig()
    return _config


def reload_config() -> BrainConfig:
    """Reload configuration from environment"""
    global _config
    _config = BrainConfig()
    return _config


# Feature flags for easy checking
class Features:
    """Feature flags for quick access"""
    
    @staticmethod
    def knowledge_enabled() -> bool:
        return get_config().elasticsearch.enabled
    
    @staticmethod
    def search_enabled() -> bool:
        return get_config().meilisearch.enabled
    
    @staticmethod
    def web_intel_enabled() -> bool:
        return get_config().crawl4ai.enabled
    
    @staticmethod
    def automation_enabled() -> bool:
        return get_config().browser_use.enabled
    
    @staticmethod
    def code_execution_enabled() -> bool:
        return get_config().code_execution.enabled
    
    @staticmethod
    def image_gen_enabled() -> bool:
        return get_config().stable_diffusion.enabled
    
    @staticmethod
    def caching_enabled() -> bool:
        return get_config().redis.enabled


# ============================================================================
# LEGACY COMPATIBILITY (for backward compatibility with website imports)
# ============================================================================
# Stub for legacy OPENROUTER_CONFIG to prevent import errors
OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "models": {},
    "api_keys": {}
}

def get_openrouter_headers(api_key_name: str = "default") -> dict:
    """Legacy function stub for OpenRouter headers"""
    return {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
        "HTTP-Referer": "https://companion.ai",
        "X-Title": "Companion AI"
    }

def get_model_config(model_name: str) -> dict:
    """Legacy function stub for model config"""
    return OPENROUTER_CONFIG["models"].get(model_name, {})

# Export commonly used configs
__all__ = [
    'BrainConfig',
    'BytezConfig',
    'ElasticsearchConfig',
    'MeilisearchConfig',
    'Crawl4AIConfig',
    'BrowserUseConfig',
    'PublicAPIsConfig',
    'CodeExecutionConfig',
    'StableDiffusionConfig',
    'RedisConfig',
    'get_config',
    'reload_config',
    'Features',
    'OPENROUTER_CONFIG',  # Legacy compatibility
    'get_openrouter_headers',  # Legacy compatibility
    'get_model_config'  # Legacy compatibility
]
