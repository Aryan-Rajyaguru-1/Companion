"""
Local Intelligence Core - Week 1
================================
Ollama integration for local models with auto-download, management,
and hybrid inference (local + cloud fallback).

This module enables the brain to:
- Run models locally without API dependencies
- Auto-download and manage models
- Fallback to cloud when needed
- Orchestrate multiple models intelligently
"""

import os
import json
import asyncio
import subprocess
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import httpx
from pathlib import Path


class ModelSource(Enum):
    """Source of model execution"""
    LOCAL_OLLAMA = "local_ollama"
    CLOUD_BYTEZ = "cloud_bytez"
    CLOUD_OPENROUTER = "cloud_openrouter"
    HYBRID = "hybrid"


@dataclass
class ModelInfo:
    """Information about a model"""
    name: str
    source: ModelSource
    size_gb: float
    capabilities: List[str]
    downloaded: bool = False
    last_used: Optional[float] = None


class OllamaManager:
    """
    Manages Ollama installation and model lifecycle.
    Handles auto-download, updates, and local serving.
    """
    
    def __init__(self, models_dir: str = "~/.ollama/models"):
        self.models_dir = Path(models_dir).expanduser()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.base_url = "http://localhost:11434"
        self.available_models = {}
        self.downloaded_models = set()
        
        # Model catalog - including user's installed models
        self.model_catalog = {
            'llama3.2:3b': ModelInfo(
                name='llama3.2:3b',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=2.0,
                capabilities=['reasoning', 'general', 'chat', 'analysis']
            ),
            'codegemma:2b': ModelInfo(
                name='codegemma:2b',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=1.6,
                capabilities=['coding', 'technical', 'debugging', 'efficient']
            ),
            'codeqwen:7b': ModelInfo(
                name='codeqwen:7b',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=4.2,
                capabilities=['coding', 'reasoning', 'multilingual', 'advanced']
            ),
            'deepseek-r1:1.5b': ModelInfo(
                name='deepseek-r1:1.5b',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=1.1,
                capabilities=['reasoning', 'logical', 'efficient', 'fast']
            ),
            # Additional popular models
            'llama3.2:latest': ModelInfo(
                name='llama3.2:latest',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=2.0,
                capabilities=['reasoning', 'general', 'chat']
            ),
            'mistral': ModelInfo(
                name='mistral:latest',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=4.1,
                capabilities=['reasoning', 'creative', 'multilingual']
            ),
            'codellama': ModelInfo(
                name='codellama:latest',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=3.8,
                capabilities=['coding', 'technical', 'debugging']
            ),
            'phi3': ModelInfo(
                name='phi3:latest',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=2.3,
                capabilities=['reasoning', 'efficient', 'chat']
            ),
            'deepseek-coder': ModelInfo(
                name='deepseek-coder:latest',
                source=ModelSource.LOCAL_OLLAMA,
                size_gb=6.7,
                capabilities=['coding', 'reasoning', 'technical']
            ),
        }
        
    async def check_ollama_installed(self) -> bool:
        """Check if Ollama is installed and running"""
        try:
            result = subprocess.run(['which', 'ollama'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode != 0:
                return False
                
            # Check if Ollama server is running
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{self.base_url}/api/tags", timeout=2.0)
                    return response.status_code == 200
                except:
                    return False
        except Exception:
            return False
    
    async def install_ollama(self) -> bool:
        """Auto-install Ollama if not present"""
        print("🔧 Ollama not found. Installing...")
        try:
            # Download and install Ollama
            install_cmd = "curl -fsSL https://ollama.com/install.sh | sh"
            result = subprocess.run(install_cmd, 
                                  shell=True, 
                                  capture_output=True, 
                                  text=True,
                                  timeout=300)
            
            if result.returncode == 0:
                print("✅ Ollama installed successfully!")
                
                # Start Ollama service
                await self.start_ollama_service()
                return True
            else:
                print(f"❌ Failed to install Ollama: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error installing Ollama: {e}")
            return False
    
    async def start_ollama_service(self):
        """Start Ollama service in background"""
        try:
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            # Wait for service to start
            await asyncio.sleep(3)
            print("✅ Ollama service started")
        except Exception as e:
            print(f"⚠️ Could not start Ollama service: {e}")
    
    async def list_downloaded_models(self) -> List[str]:
        """Get list of downloaded models"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    models = [m['name'] for m in data.get('models', [])]
                    self.downloaded_models = set(models)
                    return models
                return []
        except Exception as e:
            print(f"⚠️ Could not list models: {e}")
            return []
    
    async def download_model(self, model_name: str) -> bool:
        """Download a model via Ollama"""
        print(f"📥 Downloading model: {model_name}")
        try:
            # Use Ollama CLI to pull model
            process = await asyncio.create_subprocess_exec(
                'ollama', 'pull', model_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print(f"✅ Downloaded {model_name}")
                self.downloaded_models.add(model_name)
                return True
            else:
                print(f"❌ Failed to download {model_name}: {stderr.decode()}")
                return False
        except Exception as e:
            print(f"❌ Error downloading {model_name}: {e}")
            return False
    
    async def auto_select_models(self, task_type: str = 'general') -> List[str]:
        """Auto-select best models for task type based on installed models"""
        # Map task types to preferred models (prioritize installed models)
        task_model_map = {
            'coding': ['codeqwen:7b', 'codegemma:2b', 'codellama', 'deepseek-coder'],
            'creative': ['llama3.2:3b', 'mistral', 'llama3.2'],
            'reasoning': ['deepseek-r1:1.5b', 'llama3.2:3b', 'phi3', 'mistral'],
            'general': ['llama3.2:3b', 'phi3', 'llama3.2'],
            'technical': ['codeqwen:7b', 'deepseek-r1:1.5b', 'deepseek-coder', 'codellama'],
            'fast': ['deepseek-r1:1.5b', 'codegemma:2b', 'llama3.2:3b']
        }
        
        preferred = task_model_map.get(task_type, ['llama3.2:3b', 'llama3.2'])
        
        # Check which are downloaded
        available = []
        for model in preferred:
            # Try exact match first
            if model in self.downloaded_models:
                available.append(model)
            # Try with :latest suffix
            elif f"{model}:latest" in self.downloaded_models:
                available.append(f"{model}:latest")
        
        # If none found, use any available model
        if not available and self.downloaded_models:
            available.append(list(self.downloaded_models)[0])
        
        # If still none, download first preferred
        if not available and preferred:
            model_to_download = preferred[0]
            if await self.download_model(model_to_download):
                available.append(model_to_download)
        
        return available
    
    async def query_local(self, model: str, prompt: str, 
                         temperature: float = 0.7,
                         max_tokens: int = 2000) -> Optional[Dict[str, Any]]:
        """Query a local Ollama model"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        'model': model,
                        'prompt': prompt,
                        'temperature': temperature,
                        'options': {
                            'num_predict': max_tokens
                        }
                    }
                )
                
                if response.status_code == 200:
                    # Parse streaming response
                    result = ""
                    for line in response.text.strip().split('\n'):
                        if line:
                            data = json.loads(line)
                            result += data.get('response', '')
                    
                    return {
                        'response': result.strip(),
                        'model': model,
                        'source': ModelSource.LOCAL_OLLAMA.value
                    }
                else:
                    return None
        except Exception as e:
            print(f"⚠️ Local query failed for {model}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Ollama manager statistics"""
        return {
            'downloaded_models': list(self.downloaded_models),
            'available_models': list(self.model_catalog.keys()),
            'models_dir': str(self.models_dir)
        }


class HybridInferenceEngine:
    """
    Orchestrates local and cloud models intelligently.
    Tries local first, falls back to cloud if needed.
    """
    
    def __init__(self, ollama_manager: OllamaManager, cloud_client: Any = None):
        self.ollama = ollama_manager
        self.cloud_client = cloud_client
        
        self.stats = {
            'local_calls': 0,
            'cloud_calls': 0,
            'fallback_count': 0,
            'total_latency_local': 0.0,
            'total_latency_cloud': 0.0
        }
    
    async def infer(self, prompt: str, 
                   task_type: str = 'general',
                   prefer_local: bool = False,  # Changed default to False - prioritize cloud
                   timeout: float = 30.0) -> Dict[str, Any]:
        """
        Intelligent inference with hybrid approach.
        
        Strategy:
        1. Try cloud first (default - faster responses)
        2. Fallback to local if cloud fails/unavailable
        3. Can force local with prefer_local=True
        """
        import time
        
        result = None
        
        # Try local first (only if explicitly requested)
        if prefer_local:
            local_models = await self.ollama.auto_select_models(task_type)
            
            if local_models:
                start = time.time()
                result = await self.ollama.query_local(local_models[0], prompt)
                latency = time.time() - start
                
                if result:
                    self.stats['local_calls'] += 1
                    self.stats['total_latency_local'] += latency
                    result['latency'] = latency
                    result['source'] = ModelSource.LOCAL_OLLAMA.value
                    return result
        
        # Fallback to cloud
        if self.cloud_client:
            try:
                start = time.time()
                
                # Use existing cloud infrastructure
                cloud_response = await self.cloud_client.query(prompt, task_type)
                
                latency = time.time() - start
                self.stats['cloud_calls'] += 1
                self.stats['total_latency_cloud'] += latency
                self.stats['fallback_count'] += 1
                
                return {
                    'response': cloud_response,
                    'model': 'cloud',
                    'source': ModelSource.CLOUD_BYTEZ.value,
                    'latency': latency
                }
            except Exception as e:
                print(f"❌ Cloud fallback failed: {e}")
                return {
                    'response': "Error: Both local and cloud inference failed.",
                    'error': str(e)
                }
        
        return {
            'response': "Error: No inference engine available.",
            'error': 'No local or cloud models available'
        }
    
    async def multi_model_orchestration(self, prompt: str,
                                       models: Optional[List[str]] = None,
                                       strategy: str = 'parallel') -> List[Dict[str, Any]]:
        """
        Query multiple models and orchestrate results.
        
        Strategies:
        - parallel: Query all models simultaneously
        - cascade: Try models in sequence until success
        - consensus: Get agreement from multiple models
        """
        if strategy == 'parallel':
            # Query all models in parallel
            tasks = []
            for model in (models or await self.ollama.list_downloaded_models()):
                tasks.append(self.ollama.query_local(model, prompt))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            valid_results: List[Dict[str, Any]] = []
            for r in results:
                if r and not isinstance(r, Exception) and isinstance(r, dict):
                    valid_results.append(r)
            return valid_results
        
        elif strategy == 'cascade':
            # Try models in sequence
            for model in (models or await self.ollama.list_downloaded_models()):
                result = await self.ollama.query_local(model, prompt)
                if result:
                    return [result]
            return []
        
        elif strategy == 'consensus':
            # Get multiple responses for consensus
            results = []
            for model in (models or await self.ollama.list_downloaded_models())[:3]:
                result = await self.ollama.query_local(model, prompt)
                if result:
                    results.append(result)
            return results
        
        # Default fallback
        return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get inference statistics"""
        total_calls = self.stats['local_calls'] + self.stats['cloud_calls']
        
        return {
            'local_calls': self.stats['local_calls'],
            'cloud_calls': self.stats['cloud_calls'],
            'fallback_count': self.stats['fallback_count'],
            'local_percentage': (self.stats['local_calls'] / total_calls * 100) if total_calls > 0 else 0,
            'avg_latency_local': (self.stats['total_latency_local'] / self.stats['local_calls']) if self.stats['local_calls'] > 0 else 0,
            'avg_latency_cloud': (self.stats['total_latency_cloud'] / self.stats['cloud_calls']) if self.stats['cloud_calls'] > 0 else 0
        }


class LocalIntelligenceCore:
    """
    Main interface for local intelligence.
    Combines Ollama management and hybrid inference.
    """
    
    def __init__(self, auto_setup: bool = True, cloud_client: Any = None):
        self.ollama = OllamaManager()
        self.hybrid_engine = HybridInferenceEngine(self.ollama, cloud_client)
        self.initialized = False
        
        if auto_setup:
            # Try to setup async if event loop exists, otherwise skip
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._async_setup())
            except RuntimeError:
                # No event loop running, skip async setup
                self.initialized = True
    
    async def _async_setup(self):
        """Async initialization"""
        # Check Ollama
        if not await self.ollama.check_ollama_installed():
            print("⚠️ Ollama not found. Install with: curl -fsSL https://ollama.com/install.sh | sh")
            print("   Then run: ollama serve")
            # Auto-install disabled by default for safety
            # await self.ollama.install_ollama()
        else:
            print("✅ Ollama detected and running")
        
        # List available models
        models = await self.ollama.list_downloaded_models()
        
        if models:
            print(f"✅ Found {len(models)} installed models:")
            for model in models:
                print(f"   • {model}")
        else:
            print("⚠️ No models found. You can download models with:")
            print("   ollama pull llama3.2:3b")
            print("   ollama pull codegemma:2b")
        
        self.initialized = True
        print(f"✅ Local Intelligence Core initialized")
    
    async def think(self, prompt: str, task_type: str = 'general',
                   prefer_local: bool = False) -> Dict[str, Any]:
        """Main thinking interface - defaults to cloud for speed"""
        return await self.hybrid_engine.infer(prompt, task_type, prefer_local)
    
    async def download_model(self, model_name: str) -> bool:
        """Download a specific model"""
        return await self.ollama.download_model(model_name)
    
    async def list_models(self) -> List[str]:
        """List available local models"""
        return await self.ollama.list_downloaded_models()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats"""
        return {
            'ollama': self.ollama.get_stats(),
            'inference': self.hybrid_engine.get_stats(),
            'initialized': self.initialized
        }


# Convenience function
async def create_local_intelligence(cloud_client: Any = None) -> LocalIntelligenceCore:
    """Create and initialize local intelligence core"""
    core = LocalIntelligenceCore(auto_setup=False, cloud_client=cloud_client)
    await core._async_setup()
    return core
