import hvac

# 1. Подключение к серверу Vault
client = hvac.Client(
    url='http://127.0.0.1:8200',  # Или ваш адрес продакшн-сервера
    token='ваш-токен'  # Используйте AppRole или другой метод для продакшена
)

# 2. Запись секрета (используется движок KV v2)
secret_data = {
    'telegram_token': '123456:ABC...',
    'akash_mnemonic': 'слово1 слово2 ...'
}
create_response = client.secrets.kv.v2.create_or_update_secret(
    path='uaia/agents/architect',
    secret=secret_data,
)
print(f"✅ Секрет записан. Версия: {create_response['version']}")

# 3. Чтение секрета
read_response = client.secrets.kv.v2.read_secret_version(
    path='uaia/agents/architect'
)
retrieved_secret = read_response['data']['data']
print(f"✅ Токен Telegram: {retrieved_secret['telegram_token']}")

# 4. Работа с динамическими секретами (например, для БД)
# database_creds = client.secrets.database.generate_credentials(
#     name='uaia-postgres-role'
# )

# Для продакшена настоятельно рекомендуется заменить простой токен на более безопасные методы аутентификации, такие как AppRole.
# https://developer.hashicorp.com/vault/docs/get-started/developer-qs
