
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

#  Nested Models 

class TokenInfo(BaseModel):
    amount: Optional[float] = 0.0
    amountUSD: Optional[float] = 0.0
    address: Optional[str] = None
    symbol: Optional[str] = None

class Transaction(BaseModel):
    document_id: Optional[str] = None
    action: Optional[str] = None
    type: Optional[str] = None  
    timestamp: Optional[int] = 0
    caller: Optional[str] = None
    protocol: Optional[str] = None
    pool: Optional[str] = None
    poolName: Optional[str] = None
    poolId: Optional[str] = None
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    tokenIn: Optional[TokenInfo] = None
    tokenOut: Optional[TokenInfo] = None
    token0: Optional[TokenInfo] = None
    token1: Optional[TokenInfo] = None
    amount_usd: Optional[float] = 0.0

class ProtocolData(BaseModel):
    protocolType: Optional[str] = None
    transactions: Optional[List[Transaction]] = Field(default_factory=list)

# Wallet Input 

class WalletInput(BaseModel):
    wallet_address: str
    data: Optional[List[ProtocolData]] = Field(default_factory=list)
    transactions: Optional[List[Transaction]] = Field(default_factory=list)

# Feature & Category Models 

class CategoryResult(BaseModel):
    category: str
    score: float
    transaction_count: int
    features: Dict[str, Any] = Field(default_factory=dict)

class WalletScoreResult(BaseModel):
    wallet_address: str
    zscore: str
    timestamp: int
    processing_time_ms: int
    categories: List[CategoryResult] = Field(default_factory=list)
    error: Optional[str] = None
