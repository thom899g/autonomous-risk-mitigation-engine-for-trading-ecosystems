"""
ARME Configuration Manager
Centralized configuration with environment variable fallbacks and validation.
"""
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ExchangeType(Enum):
    """Supported exchange types"""
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BITSTAMP = "bitstamp"
    ALPACA = "alpaca"  # For traditional markets

@dataclass
class ExchangeConfig:
    """Individual exchange configuration"""
    name: str
    type: ExchangeType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sandbox: bool = True  # Default to sandbox for safety
    symbols: List[str] = field(default_factory=list)
    update_frequency_ms: int = 1000
    enabled: bool = True
    
    def __post_init__(self):
        """Validate configuration"""
        if not self.symbols:
            raise ValueError(f"Exchange {self.name} must have at least one symbol")
        if self.update_frequency_ms < 100:
            raise ValueError("Update frequency must be at least 100ms")
        if self.type in [ExchangeType.BINANCE, ExchangeType.KRAKEN] and not (self.api_key and self.api_secret):
            logging.warning(f"{self.name} requires API credentials for full functionality")

@dataclass
class FirestoreConfig:
    """Firebase Firestore configuration"""
    project_id: str
    credentials_path: str = "firebase-credentials.json"
    collections: Dict[str, str] = field(default_factory=lambda: {
        "raw_ticks": "raw_ticks",
        "order_books": "order_books",
        "system_health": "system_health",
        "market_regimes": "market_regimes"
    })
    batch_size: int = 500
    timeout_seconds: int = 30

@dataclass
class RiskConfig:
    """Risk management parameters"""
    max_memory_usage_mb: int = 1024
    max_queue_size: int = 10000
    circuit_breaker_threshold: float = 0.15  # 15% price movement
    health_check_interval_sec: int = 30
    alert_telegram_ids: List[str] = field(default_factory=list)

class ARMEConfig:
    """Main configuration manager"""
    
    def __init__(self):
        self.exchanges: Dict[str, ExchangeConfig] = {}
        self.firestore: Optional[FirestoreConfig] = None
        self.risk: RiskConfig = RiskConfig()
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from environment and defaults"""
        try:
            # Firestore config
            project_id = os.getenv("FIRESTORE_PROJECT_ID", "arme-dev")
            self.firestore = FirestoreConfig(
                project_id=project_id,
                credentials_path=os.getenv("FIRESTORE_CREDENTIALS_PATH", "firebase-credentials.json")
            )
            
            # Load exchanges from JSON or environment
            exchanges_json = os.getenv("EXCHANGES_CONFIG", "[]")
            exchanges_data = json.loads(exchanges_json) if exchanges_json else []
            
            # Default exchanges if none configured
            if not exchanges_data:
                exchanges_data = [
                    {
                        "name": "Binance_Test",
                        "type": "binance",
                        "symbols": ["BTC/USDT", "ETH/USDT"],
                        "sandbox": True
                    }
                ]
            
            for exchange_data in exchanges_data:
                exchange = ExchangeConfig(
                    name=exchange_data["name"],
                    type=ExchangeType(exchange_data["type"]),
                    api_key=os.getenv(f"{exchange_data['name'].upper()}_API_KEY"),
                    api_secret=os.getenv(f"{exchange_data['name'].upper()}_API_SECRET"),
                    symbols=exchange_data["symbols"],
                    sandbox=exchange_data.get("sandbox", True),
                    update_frequency_ms=exchange_data.get("update_frequency_ms", 1000)
                )
                self.exchanges[exchange.name] = exchange
            
            # Risk config
            self.risk.alert_telegram_ids = json.loads(
                os.getenv("TELEGRAM_ALERT_IDS", "[]")
            )
            
            logging.info("Configuration loaded successfully")
            
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            raise
    
    def get_enabled_exchanges(self) -> List[ExchangeConfig]:
        """Get list of enabled exchanges"""
        return [ex for ex in self.exchanges.values() if ex.enabled]
    
    def validate(self) -> bool:
        """Validate all configurations"""
        try:
            if not self.firestore:
                raise ValueError("Firestore configuration missing")
            
            if not os.path.exists(self.firestore.credentials_path):
                logging.warning(f"Firebase credentials file not found: {self.firestore.credentials_path}")
            
            enabled = self.get_enabled_exchanges()
            if not enabled:
                raise ValueError("No enabled exchanges configured")
            
            return True
            
        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            return False

# Global config instance
config = ARMEConfig()