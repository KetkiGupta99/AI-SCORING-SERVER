
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from app.utils.types import WalletInput, WalletScoreResult

# Type aliases for clarity
TransactionDict = Dict[str, Any]
LPFeatures = Dict[str, float]
SwapFeatures = Dict[str, float]

# Divide a by b safely, return default if division fails or b is zero
def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    try:
        return a / b if b != 0 else default
    except Exception:
        return default

def _amount_from_swap(tx: TransactionDict) -> float:
    # Extract USD value from swap transaction, considering multiple possible fields
    if "amount_usd" in tx and tx["amount_usd"] is not None:
        return float(tx["amount_usd"])
    t_in = tx.get("tokenIn") or tx.get("token_in")
    t_out = tx.get("tokenOut") or tx.get("token_out")
    if isinstance(t_in, dict) and t_in.get("amountUSD") not in (None, ""):
        return float(t_in.get("amountUSD", 0.0))
    if isinstance(t_out, dict) and t_out.get("amountUSD") not in (None, ""):
        return float(t_out.get("amountUSD", 0.0))
    usd0 = float(tx.get("token0", {}).get("amountUSD", 0.0) or 0.0)
    usd1 = float(tx.get("token1", {}).get("amountUSD", 0.0) or 0.0)
    return usd0 + usd1

def _extract_amount_usd(tx: TransactionDict) -> float:
    # Generalized USD amount extraction for any transaction type
    if "amount_usd" in tx and tx["amount_usd"] is not None:
        return float(tx["amount_usd"])
    if "amountUSD" in tx and tx["amountUSD"] is not None:
        return float(tx["amountUSD"])
    action = (tx.get("action") or tx.get("type") or "").lower()
    if action == "swap":
        return _amount_from_swap(tx)
    usd0 = float(tx.get("token0", {}).get("amountUSD", 0.0) or 0.0)
    usd1 = float(tx.get("token1", {}).get("amountUSD", 0.0) or 0.0)
    return usd0 + usd1

def _safe_symbol_from_field(field: Optional[Dict[str, Any]]) -> Optional[str]:
    # Safely extract token symbol from a dict field if exists
    return field.get("symbol") if isinstance(field, dict) else None

# Preprocessing 

def build_transactions_list(wallet_input: WalletInput) -> List[TransactionDict]:

    #Standardize wallet input into a flat list of transactions with common fields: type, amount_usd, pool, timestamp, token_in, token_out
    txs_out: List[TransactionDict] = []

    raw_top_txs = wallet_input.get("transactions")
    if raw_top_txs:
        for tx in raw_top_txs:
            action = (tx.get("type") or tx.get("action") or "").lower()
            txs_out.append({
                "type": action,
                "amount_usd": _extract_amount_usd(tx),
                "pool": tx.get("pool") or tx.get("poolName") or tx.get("poolId"),
                "timestamp": int(tx.get("timestamp", 0) or 0),
                "token_in": tx.get("token_in") or _safe_symbol_from_field(tx.get("tokenIn")) or _safe_symbol_from_field(tx.get("token0")),
                "token_out": tx.get("token_out") or _safe_symbol_from_field(tx.get("tokenOut")) or _safe_symbol_from_field(tx.get("token1")),
            })
        return txs_out
    
    # wallet_input["data"] contains transactions

    for entry in wallet_input.get("data", []):
        for tx in entry.get("transactions", []):
            action = (tx.get("action") or tx.get("type") or "").lower()
            txs_out.append({
                "type": action,
                "amount_usd": _extract_amount_usd(tx),
                "pool": tx.get("pool") or tx.get("poolName") or tx.get("poolId"),
                "timestamp": int(tx.get("timestamp", 0) or 0),
                "token_in": _safe_symbol_from_field(tx.get("tokenIn")) or _safe_symbol_from_field(tx.get("token0")) or tx.get("token_in"),
                "token_out": _safe_symbol_from_field(tx.get("tokenOut")) or _safe_symbol_from_field(tx.get("token1")) or tx.get("token_out"),
            })
    return txs_out

# Feature Extraction 

def extract_lp_features(df: pd.DataFrame) -> LPFeatures:
    # Compute liquidity provider features from transactions DataFrame
    deposits = df[df["type"] == "deposit"]
    withdraws = df[df["type"] == "withdraw"]

    total_deposit_usd = deposits["amount_usd"].sum() if not deposits.empty else 0.0
    total_withdraw_usd = withdraws["amount_usd"].sum() if not withdraws.empty else 0.0
    num_deposits = len(deposits)
    num_withdraws = len(withdraws)
    withdraw_ratio = safe_divide(total_withdraw_usd, total_deposit_usd)

    # Average holding time in days for deposits -> withdrawals

    if not deposits.empty and not withdraws.empty:
        avg_hold_time_days = (withdraws["timestamp"].max() - deposits["timestamp"].min()) / 86400.0
    else:
        avg_hold_time_days = 0.0

    account_age_days = safe_divide((df["timestamp"].max() - df["timestamp"].min()), 86400.0)
    unique_pools = int(df[df["type"].isin(["deposit", "withdraw"])]["pool"].nunique())

    features: LPFeatures = {
        "total_deposit_usd": float(total_deposit_usd),
        "total_withdraw_usd": float(total_withdraw_usd),
        "num_deposits": int(num_deposits),
        "num_withdraws": int(num_withdraws),
        "withdraw_ratio": float(withdraw_ratio),
        "avg_hold_time_days": float(avg_hold_time_days),
        "account_age_days": float(account_age_days),
        "unique_pools": int(unique_pools),
    }
    return {k: (0.0 if not np.isfinite(v) else v) for k, v in features.items()}

def extract_swap_features(df: pd.DataFrame) -> SwapFeatures:

    # Compute swap-related features from transactions DataFrame
    swaps = df[df["type"] == "swap"]

    total_swap_volume = float(swaps["amount_usd"].sum()) if not swaps.empty else 0.0
    num_swaps = int(len(swaps))
    unique_pools_swapped = int(swaps["pool"].nunique()) if not swaps.empty else 0
    avg_swap_size = float(safe_divide(total_swap_volume, num_swaps))

    if not swaps.empty:
        token_in_count = swaps["token_in"].nunique(dropna=True)
        token_out_count = swaps["token_out"].nunique(dropna=True)
        token_diversity_score = float((int(token_in_count) + int(token_out_count)) * 5)
    else:
        token_diversity_score = 0.0

    active_days = safe_divide((df["timestamp"].max() - df["timestamp"].min()), 86400.0, 1.0)
    swap_frequency_score = float(safe_divide(num_swaps, active_days))

    features: SwapFeatures = {
        "total_swap_volume": float(total_swap_volume),
        "num_swaps": int(num_swaps),
        "unique_pools_swapped": int(unique_pools_swapped),
        "avg_swap_size": float(avg_swap_size),
        "token_diversity_score": float(token_diversity_score),
        "swap_frequency_score": float(swap_frequency_score),
    }
    return {k: (0.0 if not np.isfinite(v) else v) for k, v in features.items()}

#  Scoring

def score_lp(features: LPFeatures) -> float:
    # Compute LP score using deposits, withdraw ratio, holding time, and pool diversity
    score = 0.0
    score += min(features["total_deposit_usd"] / 10.0, 300.0)
    score += (1.0 - features["withdraw_ratio"]) * 100.0
    score += (min(features["avg_hold_time_days"], 365.0) / 365.0) * 200.0
    score += features["unique_pools"] * 20.0
    return float(min(score, 1000.0))

def score_swap(features: SwapFeatures) -> float:
    # Compute swap score using volume, count, token diversity, and frequency
    score = 0.0
    score += min(features["total_swap_volume"] / 20.0, 300.0)
    score += min(features["num_swaps"] * 5.0, 200.0)
    score += features["token_diversity_score"]
    score += min(features["swap_frequency_score"] * 100.0, 100.0)
    return float(min(score, 1000.0))

def aggregate_scores(lp_score: float, swap_score: float) -> float:
    # Combine LP and swap scores with weighted average (60% LP, 40% swap)
    return round((0.6 * lp_score + 0.4 * swap_score), 2)

# Main Processor 
def process_wallet(wallet_input: WalletInput) -> WalletScoreResult:
    start = time.time()
    try:
        transactions: List[TransactionDict] = build_transactions_list(wallet_input)

        # Return zero-score if no transactions exist

        if not transactions:
            return {
                "wallet_address": wallet_input.get("wallet_address", "unknown"),
                "zscore": "0.0",
                "timestamp": int(time.time()),
                "processing_time_ms": int((time.time() - start) * 1000),
                "categories": [
                    {"category": "dexes", "score": 0.0, "transaction_count": 0, "features": {}}
                ]
            }
        
        # Convert to DataFrame for numeric calculation
        df = pd.DataFrame(transactions)
        df["timestamp"] = pd.to_numeric(df.get("timestamp", 0), errors="coerce").fillna(0).astype(int)
        df["amount_usd"] = pd.to_numeric(df.get("amount_usd", 0.0), errors="coerce").fillna(0.0).astype(float)

        # Extract features
        lp_features = extract_lp_features(df)
        swap_features = extract_swap_features(df)

        # Score calculation
        lp_score_val = score_lp(lp_features)
        swap_score_val = score_swap(swap_features)
        final_score = aggregate_scores(lp_score_val, swap_score_val)

        # structured output
        result: WalletScoreResult = {
            "wallet_address": wallet_input.get("wallet_address", "unknown"),
            "zscore": f"{final_score:.18f}",  
            "timestamp": int(time.time()),
            "processing_time_ms": int((time.time() - start) * 1000),
            "categories": [
                {
                    "category": "dexes",
                    "score": final_score,
                    "transaction_count": len(df),
                    "features": {**lp_features, **swap_features,
                                 "lp_score": lp_score_val,
                                 "swap_score": swap_score_val}
                }
            ]
        }
        return result

    except Exception as e:
        # Return error info if processing fails
        return {
            "wallet_address": wallet_input.get("wallet_address", "unknown"),
            "zscore": "0.0",
            "timestamp": int(time.time()),
            "processing_time_ms": int((time.time() - start) * 1000),
            "categories": [],
            "error": str(e),
        }

# Standalone Run
# if __name__ == "__main__":
#     sample_wallet = {
#     "wallet_address": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
#     "data": [
#         {
#             "protocolType": "dexes",
#             "transactions": [
#                 {
#                     "document_id": "507f1f77bcf86cd799439011",
#                     "action": "swap",
#                     "timestamp": 1703980800,
#                     "caller": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
#                     "protocol": "uniswap_v3",
#                     "poolId": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
#                     "poolName": "Uniswap V3 USDC/WETH 0.05%",
#                     "tokenIn": {
#                         "amount": 1000000000,
#                         "amountUSD": 1000.0,
#                         "address": "0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3",
#                         "symbol": "USDC"
#                     },
#                     "tokenOut": {
#                         "amount": 500000000000000000,
#                         "amountUSD": 1000.0,
#                         "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
#                         "symbol": "WETH"
#                     }
#                 },
#                 {
#                     "document_id": "507f1f77bcf86cd799439012",
#                     "action": "deposit",
#                     "timestamp": 1703980900,
#                     "caller": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
#                     "protocol": "uniswap_v3",
#                     "poolId": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
#                     "poolName": "Uniswap V3 USDC/WETH 0.05%",
#                     "token0": {
#                         "amount": 500000000,
#                         "amountUSD": 500.0,
#                         "address": "0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3",
#                         "symbol": "USDC"
#                     },
#                     "token1": {
#                         "amount": 250000000000000000,
#                         "amountUSD": 500.0,
#                         "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
#                         "symbol": "WETH"
#                     }
#                 },
#                 {
#                     "document_id": "507f1f77bcf86cd799439013",
#                     "action": "withdraw",
#                     "timestamp": 1703981800,
#                     "caller": "0x742d35Cc6634C0532925a3b8D4C9db96590e4265",
#                     "protocol": "uniswap_v3",
#                     "poolId": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
#                     "poolName": "Uniswap V3 USDC/WETH 0.05%",
#                     "token0": {
#                         "amount": 250000000,
#                         "amountUSD": 250.0,
#                         "address": "0xa0b86a33e6c3d4c3e6c3d4c3e6c3d4c3e6c3d4c3",
#                         "symbol": "USDC"
#                     },
#                     "token1": {
#                         "amount": 125000000000000000,
#                         "amountUSD": 250.0,
#                         "address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
#                         "symbol": "WETH"
#                     }
#                 }
#             ]
#         }
#     ]
# }


#     res = process_wallet(sample_wallet)
#     print(json.dumps(res, indent=2))
