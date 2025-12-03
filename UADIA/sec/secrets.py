import base64
import json
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# === 1. ФУНКЦИИ ШИФРОВАНИЯ (Остаются прежними) ===
def derive_key_from_seed(seed_phrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key_material = seed_phrase.encode()
    key = base64.urlsafe_b64encode(kdf.derive(key_material))
    return key

def encrypt_secret(secret_data: dict, key: bytes) -> str:
    f = Fernet(key)
    secret_json = json.dumps(secret_data).encode()
    encrypted_data = f.encrypt(secret_json)
    return base64.urlsafe_b64encode(encrypted_data).decode()

def decrypt_secret(encrypted_payload: str, key: bytes) -> Dict:
    f = Fernet(key)
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_payload.encode())
    decrypted_bytes = f.decrypt(encrypted_bytes)
    return json.loads(decrypted_bytes.decode())

# === 2. ЗАПИСЬ В БЛОКЧЕЙН (с использованием суммы) ===
from akash.client import AkashClient
from akash.wallet import AkashWallet

def write_secret_to_blockchain(
    wallet: AkashWallet,
    client: AkashClient,
    encrypted_payload: str,
    amount_code: int = 1000  # Сумма как часть "кода"
) -> Optional[str]:
    """
    Отправляет транзакцию самому себе с секретом в memo.
    Возвращает хэш транзакции (tx_hash) для записи в лог агента.
    """
    try:
        result = client.bank.send(
            wallet=wallet,
            to_address=wallet.address,  # Отправляем самому себе
            amount=str(amount_code),     # Сумма в uakt (может нести код, например 1000 = "START")
            memo=encrypted_payload,      # Зашифрованный секрет
            denom="uakt"
        )
        if result.success:
            print(f"✅ Секрет записан в tx: {result.tx_hash}")
            # КРИТИЧЕСКИ ВАЖНО: Агент должен сохранить этот tx_hash!
            # Например, в локальный файл, базу данных или другой блокчейн.
            log_transaction(wallet.address, result.tx_hash, amount_code)
            return result.tx_hash
        else:
            print(f"❌ Ошибка: {result.raw_log}")
            return None
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

def log_transaction(address: str, tx_hash: str, amount: int):
    """Простая логика записи хэша в файл. В реальности это может быть база данных."""
    with open(f"uaia_transactions_{address[-8:]}.log", "a") as f:
        f.write(f"{tx_hash},{amount}\n")

# === 3. ЧТЕНИЕ И РАСШИФРОВКА (Поиск по своим транзакциям) ===
def find_and_decrypt_secrets(
    wallet: AkashWallet,
    client: AkashClient,
    key: bytes,
    from_block: int = 0
) -> list:
    """
    Ищет все транзакции от/к адресу агента, начиная с блока from_block.
    Пытается расшифровать memo каждой как секрет.
    """
    secrets_found = []
    # Ищем транзакции по адресу (это примерный псевдокод, т.к. akash-python-sdk
    # может не иметь прямой функции поиска по истории)
    # Альтернатива: использовать akash query tx --events...
    transactions = client.query.get_transactions_by_address(
        wallet.address,
        start_block=from_block
    )
    for tx in transactions:
        # Проверяем, наша ли это транзакция (отправитель == получатель == наш адрес)
        if tx.from_address == wallet.address and tx.to_address == wallet.address:
            encrypted_memo = tx.memo
            try:
                secret = decrypt_secret(encrypted_memo, key)
                secrets_found.append({
                    'tx_hash': tx.hash,
                    'amount': tx.amount,
                    'secret': secret
                })
                print(f"🔍 Найден секрет в tx: {tx.hash}")
            except Exception:
                # Если не расшифровалось, значит это не наш секрет или битые данные
                continue
    return secrets_found

# === ПРИМЕР ИСПОЛЬЗОВАНИЯ ===
# 1. Инициализация
seed_phrase = "сид фраза УАДИА"
salt = b'uaia_salt_'
encryption_key = derive_key_from_seed(seed_phrase, salt)

# 2. Создание секрета
my_secrets = {
    "service": "telegram_bot_prod",
    "token": "123456:ABCdef...",
    "expires": "2024-12-31"
}
encrypted_payload = encrypt_secret(my_secrets, encryption_key)

# 3. Запись в блокчейн (делается один раз)
# Предполагаем, что wallet и client уже инициализированы
# tx_hash = write_secret_to_blockchain(wallet, client, encrypted_payload, amount_code=1001)

# 4. Позже: поиск и расшифровка (делается агентом при запуске)
# found = find_and_decrypt_secrets(wallet, client, encryption_key, from_block=1234567)
# for item in found:
#     print(f"Сумма: {item['amount']}uakt, Данные: {item['secret']}")
