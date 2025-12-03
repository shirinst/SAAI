from akash.client import AkashClient
from akash.wallet import AkashWallet

# 1. Создание или восстановление кошелька
wallet = AkashWallet.generate()  # Новый кошелек
# wallet = AkashWallet.from_mnemonic(input("ваша мнемоническая фраза"))  # Восстановление

print(f"Адрес: {wallet.address}")

# 2. Подключение к сети
client = AkashClient("https://rpc.akashnet.net:443")
if client.health_check():
    print("✅ Подключено к Akash mainnet")

# 3. Проверка баланса
balance = client.bank.get_balance(wallet.address, "uakt")  # Баланс в микро-единицах
balance_akt = int(balance) / 1_000_000
print(f"Баланс: {balance_akt:.6f} AKT")

# 4. Отправка транзакции (например, AKT)
recipient_address = input("akash1destinationaddress...")
result = client.bank.send(
    wallet=wallet,
    to_address=recipient_address,
    amount="1000000",  # 1 AKT
    memo="Тест от УАДИА"
)

if result.success:
    print(f"✅ Успех! Хэш: {result.tx_hash}")
else:
    print(f"❌ Ошибка: {result.raw_log}")
