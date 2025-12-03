import asyncio
from typing import List, Dict, Optional, Tuple
from cosmpy.aerial.client import LedgerClient, NetworkConfig
from cosmpy.aerial.tx import Transaction
from cosmpy.crypto.address import Address
import base64
import json
from cryptography.fernet import Fernet

class UadiaBlockchainSecretManager:
    """
    Менеджер для поиска и расшифровки секретов УАДИА из транзакций Akash.
    Использует cosmpy для доступа к блокчейну.
    """
    
    def __init__(
        self,
        rpc_url: str = "https://rpc.akashnet.net:443",
        chain_id: str = "akashnet-2",
        wallet_prefix: str = "akash"
    ):
        # Настройка сети Akash
        self.network_config = NetworkConfig(
            chain_id=chain_id,
            url=rpc_url,
            fee_minimum_gas_price=0.025,
            fee_denomination="uakt",
            staking_denomination="uakt",
        )
        # Инициализация клиента
        self.client = LedgerClient(self.network_config)
        self.wallet_prefix = wallet_prefix
        
        # Локальный кэш для ускорения последующих запросов
        self._tx_cache = {}
    
    def find_self_transfers(
        self,
        wallet_address: str,
        start_height: Optional[int] = None,
        max_pages: int = 10
    ) -> List[Dict]:
        """
        Ищет все транзакции, где отправитель И получатель == wallet_address.
        Возвращает список транзакций с их memo.
        
        Args:
            wallet_address: Адрес кошелька УАДИА (akash1...)
            start_height: Блок, с которого начинать поиск (None = с генезиса)
            max_pages: Максимальное количество страниц для пагинации
        """
        all_self_txs = []
        page = 1
        total_found = 0
        
        print(f"🔍 Начинаем поиск self-транзакций для {wallet_address}")
        
        while page <= max_pages:
            try:
                # Используем низкоуровневый запрос к RPC
                # Ищем события банковского перевода с участием нашего адреса
                query = (
                    f"message.sender='{wallet_address}' AND "
                    f"transfer.recipient='{wallet_address}'"
                )
                
                # Альтернативный, более специфичный запрос:
                # query = "message.action='/cosmos.bank.v1beta1.MsgSend'"
                
                txs_response = self.client.query_txs(
                    query=query,
                    page=page,
                    limit=50,
                    order_by="desc"
                )
                
                if not txs_response.txs:
                    print(f"📭 Страница {page}: транзакций не найдено")
                    break
                
                page_txs = []
                for tx in txs_response.txs:
                    tx_data = self._parse_transaction(tx, wallet_address)
                    if tx_data:
                        page_txs.append(tx_data)
                        total_found += 1
                
                all_self_txs.extend(page_txs)
                print(f"📄 Страница {page}: найдено {len(page_txs)} self-транзакций")
                
                # Если на странице меньше лимита, значит это последняя страница
                if len(txs_response.txs) < 50:
                    break
                    
                page += 1
                
            except Exception as e:
                print(f"⚠️ Ошибка при запросе страницы {page}: {e}")
                break
        
        print(f"✅ Всего найдено self-транзакций: {total_found}")
        return all_self_txs
    
    def _parse_transaction(
        self,
        tx_response,
        wallet_address: str
    ) -> Optional[Dict]:
        """
        Парсит транзакцию и извлекает нужные данные.
        Возвращает None, если это не self-transfer.
        """
        try:
            # Получаем Tx объект
            tx = tx_response.tx
            tx_hash = tx_response.hash
            
            # Проверяем, что это банковский перевод
            if len(tx.body.messages) == 0:
                return None
            
            msg = tx.body.messages[0]
            
            # Для Akash тип сообщения о переводе
            if msg.type_url != "/cosmos.bank.v1beta1.MsgSend":
                return None
            
            # Декодируем данные сообщения
            from_address = msg.from_address
            to_address = msg.to_address
            
            # Проверяем, что это перевод самому себе
            if from_address != wallet_address or to_address != wallet_address:
                return None
            
            # Извлекаем сумму (первая монета в списке)
            amount = "0"
            if msg.amount and len(msg.amount) > 0:
                amount = msg.amount[0].amount
            
            # Извлекаем memo
            memo = tx.body.memo if tx.body.memo else ""
            
            return {
                "hash": tx_hash,
                "height": tx_response.height,
                "amount": amount,
                "memo": memo,
                "from": from_address,
                "to": to_address,
                "timestamp": getattr(tx_response, 'timestamp', None)
            }
            
        except Exception as e:
            print(f"⚠️ Ошибка парсинга транзакции: {e}")
            return None
    
    def extract_and_decrypt_secrets(
        self,
        wallet_address: str,
        encryption_key: bytes,
        start_height: Optional[int] = None
    ) -> List[Dict]:
        """
        Основной метод: находит self-транзакции и расшифровывает их memo.
        
        Args:
            wallet_address: Адрес кошелька УАДИА
            encryption_key: Ключ для расшифровки (полученный из сид-фразы)
            start_height: Блок, с которого начинать поиск
        """
        print("=" * 60)
        print("🔐 НАЧИНАЕМ ПРОЦЕСС ИЗВЛЕЧЕНИЯ СЕКРЕТОВ УАДИА")
        print("=" * 60)
        
        # 1. Ищем self-транзакции
        transactions = self.find_self_transfers(
            wallet_address=wallet_address,
            start_height=start_height
        )
        
        # 2. Расшифровываем memo
        secrets = []
        fernet = Fernet(encryption_key)
        
        for i, tx in enumerate(transactions, 1):
            memo = tx.get("memo", "")
            if not memo:
                continue
            
            print(f"\n[{i}] Анализ транзакции: {tx['hash'][:16]}...")
            print(f"   Блок: {tx['height']}, Сумма: {tx['amount']} uakt")
            
            try:
                # Пытаемся расшифровать
                # Предполагаем, что memo уже в base64 (как мы сохраняли)
                encrypted_bytes = base64.urlsafe_b64decode(memo.encode())
                decrypted_bytes = fernet.decrypt(encrypted_bytes)
                secret_data = json.loads(decrypted_bytes.decode())
                
                # Проверяем структуру данных
                if isinstance(secret_data, dict):
                    secrets.append({
                        "tx_hash": tx["hash"],
                        "block": tx["height"],
                        "amount_code": int(tx["amount"]),
                        "data": secret_data,
                        "service": secret_data.get("service", "unknown"),
                        "timestamp": tx.get("timestamp")
                    })
                    print(f"   ✅ УСПЕХ: {secret_data.get('service', 'секрет')}")
                else:
                    print(f"   ⚠️ Данные не в ожидаемом формате")
                    
            except (base64.binascii.Error, json.JSONDecodeError):
                print(f"   ⚠️ Неверный формат memo")
            except Exception as e:
                # Любая другая ошибка (включая неверный ключ)
                print(f"   ❌ Ошибка расшифровки: {str(e)[:50]}...")
        
        print(f"\n{'='*60}")
        print(f"🎯 РЕЗУЛЬТАТ: Найдено и расшифровано {len(secrets)} секретов")
        
        # Группируем по типу сервиса
        if secrets:
            services = {}
            for secret in secrets:
                svc = secret["service"]
                services[svc] = services.get(svc, 0) + 1
            
            print("📊 Статистика по сервисам:")
            for svc, count in services.items():
                print(f"   • {svc}: {count}")
        
        return secrets

# Вспомогательные функции из предыдущих шагов
def derive_key_from_seed(seed_phrase: str, salt: bytes) -> bytes:
    """Преобразует сид-фразу в ключ шифрования (как в предыдущем коде)."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    import base64
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key_material = seed_phrase.encode()
    key = base64.urlsafe_b64encode(kdf.derive(key_material))
    return key
