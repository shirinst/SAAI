import requests
from typing import List, Dict

class SimpleUaiaSecretFinder:
    """Упрощенный поиск через API блок-эксплорера."""
    
    def __init__(self, api_base: str = "https://api.mintscan.io/v1/akash"):
        self.api_base = api_base
    
    def get_address_transactions(
        self,
        wallet_address: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Получает транзакции адреса через Mintscan API."""
        url = f"{self.api_base}/account/{wallet_address}/txs"
        params = {
            "limit": limit,
            "offset": offset,
            "order": "desc"
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка API: {e}")
            return []
    
    def find_self_transfers_simple(
        self,
        wallet_address: str,
        max_txs: int = 200
    ) -> List[Dict]:
        """Ищет self-транзакции в истории."""
        all_txs = []
        offset = 0
        limit = 50
        
        while len(all_txs) < max_txs:
            txs = self.get_address_transactions(
                wallet_address=wallet_address,
                limit=limit,
                offset=offset
            )
            
            if not txs:
                break
            
            # Фильтруем self-транзакции
            for tx in txs:
                if (tx.get("from_address") == wallet_address and 
                    tx.get("to_address") == wallet_address):
                    
                    # Проверяем, что это банковский перевод
                    if tx.get("type") == "cosmos-sdk/MsgSend":
                        all_txs.append({
                            "hash": tx["tx_hash"],
                            "height": tx["height"],
                            "amount": tx.get("amount", {}).get("amount", "0"),
                            "memo": tx.get("memo", ""),
                            "timestamp": tx.get("timestamp")
                        })
            
            offset += limit
            
            if len(txs) < limit:
                break
        
        print(f"✅ Простой поиск: найдено {len(all_txs)} self-транзакций")
        return all_txs

# Использование
simple_finder = SimpleUaiaSecretFinder()
self_txs = simple_finder.find_self_transfers_simple("akash1ваш_адрес")
