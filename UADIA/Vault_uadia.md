# 📜 Памятка по использованию HashiCorp Vault для системы УАДИА

## 🔧 1. УСТАНОВКА И НАЧАЛЬНАЯ НАСТРОЙКА

### 1.1 Установка Vault

```bash
# Для Ubuntu/Debian
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update && sudo apt install vault

# Для Linux (бинарный файл)
VAULT_VERSION="1.15.0"
wget https://releases.hashicorp.com/vault/${VAULT_VERSION}/vault_${VAULT_VERSION}_linux_amd64.zip
unzip vault_*.zip
sudo mv vault /usr/local/bin/
vault version

# Для Docker
docker pull hashicorp/vault:latest
```

### 1.2 Запуск Vault в режиме разработки

```bash
# Простой запуск (только для разработки!)
vault server -dev -dev-root-token-id="uaia-root-token"

# Экспорт переменных окружения
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='uaia-root-token'

# Проверка работы
vault status
```

### 1.3 Продакшен-развертывание

```yaml
# docker-compose.yml для продакшена
version: '3.8'
services:
  vault:
    image: hashicorp/vault:latest
    container_name: uaia-vault
    restart: unless-stopped
    ports:
      - "8200:8200"
    environment:
      VAULT_LOCAL_CONFIG: |
        ui = true
        listener "tcp" {
          address = "0.0.0.0:8200"
          tls_disable = 1  # В продакшене использовать TLS!
        }
        storage "file" {
          path = "/vault/data"
        }
      VAULT_DEV_ROOT_TOKEN_ID: "uaia-initial-token"
    volumes:
      - ./vault_data:/vault/data
    cap_add:
      - IPC_LOCK
```

### 1.4 Настройка TLS для продакшена

```bash
# Генерация SSL сертификатов
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout vault.key -out vault.crt \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=UAIA/CN=vault.uaia.network"

# Конфигурация с TLS
cat > config.hcl << EOF
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file = "/vault/certs/vault.key"
}

storage "raft" {
  path = "/vault/data"
  node_id = "uaia_node_1"
}

api_addr = "https://vault.uaia.network:8200"
cluster_addr = "https://vault.uaia.network:8201"
ui = true
EOF
```

---

## 🔐 2. АУТЕНТИФИКАЦИЯ И ПОЛИТИКИ

### 2.1 Инициализация и распечатка ключей

```bash
# Инициализация Vault
vault operator init -key-shares=5 -key-threshold=3

# Сохранение ключей распечатки (CRITICAL!)
echo "Сохраните эти ключи в безопасном месте:"
echo "1. Ключи распечатки (Unseal Keys)"
echo "2. Корневой токен (Initial Root Token)"
echo "3. Сохраните в секретном менеджере УАДИА!"

# Распечатка Vault
vault operator unseal [KEY1]
vault operator unseal [KEY2]
vault operator unseal [KEY3]
```

### 2.2 Создание политик доступа для УАДИА

```hcl
# policies/uaia-architect.hcl
path "uaia/data/architect/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "uaia/data/infra/*" {
  capabilities = ["read", "list"]
}

path "database/creds/uaia-postgres" {
  capabilities = ["read"]
}

path "pki/issue/uaia-internal" {
  capabilities = ["create", "update"]
}

# Загрузка политики
vault policy write uaia-architect policies/uaia-architect.hcl
```

### 2.3 Методы аутентификации

```bash
# Включение аутентификации через токены AppRole
vault auth enable approle

# Создание AppRole для агента УАДИА
vault write auth/approle/role/uaia-agent \
  secret_id_ttl=10m \
  token_num_uses=10 \
  token_ttl=20m \
  token_max_ttl=30m \
  secret_id_num_uses=40 \
  policies="uaia-architect"

# Получение Role ID и Secret ID
ROLE_ID=$(vault read -field=role_id auth/approle/role/uaia-agent/role-id)
SECRET_ID=$(vault write -f -field=secret_id auth/approle/role/uaia-agent/secret-id)

# Аутентификация через AppRole
vault write auth/approle/login role_id=$ROLE_ID secret_id=$SECRET_ID

# Аутентификация через Kubernetes (если УАДИА в K8s)
vault auth enable kubernetes
vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc" \
  token_reviewer_jwt="$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
```

---

## 🗝️ 3. УПРАВЛЕНИЕ СЕКРЕТАМИ ДЛЯ УАДИА

### 3.1 Включение движка секретов KV v2

```bash
# Включение движка KV v2
vault secrets enable -path=uaia kv-v2

# Альтернативный путь для разных окружений
vault secrets enable -path=uaia-prod kv-v2
vault secrets enable -path=uaia-dev kv-v2
vault secrets enable -path=uaia-staging kv-v2
```

### 3.2 Хранение секретов агентов УАДИА

```bash
# Запись секретов для архитектора УАДИА
vault kv put uaia/architect/core \
  telegram_token="123456:AAH..." \
  openai_api_key="sk-..." \
  discord_webhook="https://discord.com/api/webhooks/..." \
  akash_mnemonic="word1 word2 ... word24" \
  database_url="postgresql://user:pass@db.uaia.network:5432/uaia"

# Чтение секретов
vault kv get uaia/architect/core

# Чтение конкретного поля
vault kv get -field=telegram_token uaia/architect/core

# Обновление секрета
vault kv patch uaia/architect/core discord_webhook="https://new-webhook..."

# Удаление секрета (мягкое удаление)
vault kv delete -versions=1 uaia/architect/core

# Полное удаление
vault kv metadata delete uaia/architect/core
```

### 3.3 Организация секретов по агентам

```bash
# Секреты для разных агентов системы УАДИА
vault kv put uaia/agents/architect secrets=@architect-secrets.json
vault kv put uaia/agents/infra secrets=@infra-secrets.json
vault kv put uaia/agents/security secrets=@security-secrets.json
vault kv put uaia/agents/deploy secrets=@deploy-secrets.json
vault kv put uaia/agents/monitor secrets=@monitor-secrets.json

# Секреты для внешних сервисов
vault kv put uaia/external/akash \
  node_url="https://rpc.akashnet.net:443" \
  chain_id="akashnet-2" \
  wallet_address="akash1..."

vault kv put uaia/external/telegram \
  bot_tokens='{"main": "token1", "backup": "token2"}'

vault kv put uaia/external/apis \
  openai="sk-..." \
  anthropic="sk-ant-..." \
  cohere="..." \
  huggingface="hf_..."
```

---

## 🗄️ 4. ДИНАМИЧЕСКИЕ СЕКРЕТЫ

### 4.1 Настройка базы данных

```bash
# Включение движка баз данных
vault secrets enable database

# Настройка подключения к PostgreSQL
vault write database/config/uaia-postgres \
  plugin_name=postgresql-database-plugin \
  allowed_roles="uaia-readonly,uaia-readwrite" \
  connection_url="postgresql://{{username}}:{{password}}@postgres.uaia.network:5432/uaia" \
  username="vaultadmin" \
  password="vaultadmin-password"

# Создание роли для чтения
vault write database/roles/uaia-readonly \
  db_name=uaia-postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"

# Получение динамических учетных данных
vault read database/creds/uaia-readonly
```

### 4.2 Динамические секреты для облачных провайдеров

```bash
# AWS динамические учетные данные
vault secrets enable aws

vault write aws/config/root \
  access_key=AKIA... \
  secret_key=... \
  region=us-east-1

vault write aws/roles/uaia-s3 \
  credential_type=iam_user \
  policy_document=-<<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:*",
      "Resource": "*"
    }
  ]
}
EOF

# Получение временных AWS ключей
vault read aws/creds/uaia-s3
```

### 4.3 PKI и SSL сертификаты

```bash
# Включение движка PKI
vault secrets enable pki
vault secrets tune -max-lease-ttl=87600h pki

# Генерация корневого CA
vault write pki/root/generate/internal \
  common_name="uaia.network" \
  ttl=87600h

# Настройка URLs
vault write pki/config/urls \
  issuing_certificates="http://vault.uaia.network:8200/v1/pki/ca" \
  crl_distribution_points="http://vault.uaia.network:8200/v1/pki/crl"

# Создание роли для выдачи сертификатов
vault write pki/roles/uaia-internal \
  allowed_domains="uaia.network,internal.uaia.network" \
  allow_subdomains=true \
  max_ttl="720h"

# Генерация сертификата для агента
vault write pki/issue/uaia-internal \
  common_name="architect.internal.uaia.network" \
  ttl="24h"
```

---

## 🔗 5. ИНТЕГРАЦИЯ С СИСТЕМОЙ УАДИА

### 5.1 Python клиент для УАДИА

```python
# vault_client.py
import hvac
from typing import Dict, Optional
import os

class UaiaVaultClient:
    def __init__(self, vault_addr: str = None, token: str = None):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR')
        self.token = token or os.getenv('VAULT_TOKEN')
        self.client = hvac.Client(url=self.vault_addr, token=self.token)
        
        if not self.client.is_authenticated():
            raise Exception("Vault authentication failed")
    
    def get_agent_secrets(self, agent_name: str) -> Dict:
        """Получение секретов для конкретного агента УАДИА"""
        path = f"uaia/data/agents/{agent_name}"
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        return response['data']['data']
    
    def get_dynamic_db_creds(self, role: str = "uaia-readonly") -> Dict:
        """Получение динамических учетных данных БД"""
        response = self.client.read(f"database/creds/{role}")
        return {
            'username': response['data']['username'],
            'password': response['data']['password'],
            'lease_duration': response['lease_duration']
        }
    
    def renew_token(self) -> None:
        """Обновление токена Vault"""
        self.client.renew_self_token()
    
    def store_telegram_tokens(self, tokens: Dict[str, str]) -> None:
        """Сохранение Telegram токенов"""
        self.client.secrets.kv.v2.create_or_update_secret(
            path="uaia/external/telegram/bot_tokens",
            secret=tokens
        )
    
    @staticmethod
    def login_with_approle(vault_addr: str, role_id: str, secret_id: str):
        """Аутентификация через AppRole"""
        client = hvac.Client(url=vault_addr)
        response = client.auth.approle.login(role_id, secret_id)
        return UaiaVaultClient(vault_addr, response['auth']['client_token'])

# Использование в агентах УАДИА
vault_client = UaiaVaultClient()
secrets = vault_client.get_agent_secrets("architect")
telegram_token = secrets['telegram_token']
```

### 5.2 Конфигурация агентов через Vault

```yaml
# config/uaia-architect-config.yml
vault:
  enabled: true
  address: "http://vault.uaia.network:8200"
  auth_method: "approle"
  role_id: "{{ env.ROLE_ID }}"
  secret_id: "{{ env.SECRET_ID }}"
  secrets_path: "uaia/data/agents/architect"

telegram:
  token: "{{ vault:uaia/data/agents/architect:telegram_token }}"
  admin_ids: "{{ vault:uaia/data/agents/architect:admin_ids }}"

database:
  host: "postgres.uaia.network"
  name: "uaia"
  username: "{{ vault:dynamic:database/creds/uaia-readonly:username }}"
  password: "{{ vault:dynamic:database/creds/uaia-readonly:password }}"

apis:
  openai: "{{ vault:uaia/data/external/apis:openai }}"
  anthropic: "{{ vault:uaia/data/external/apis:anthropic }}"
```

### 5.3 Автоматическое обновление секретов

```python
# secret_renewer.py
import asyncio
import hvac
from datetime import datetime, timedelta

class UaiaSecretRenewer:
    def __init__(self, vault_client):
        self.client = vault_client
        self.renewal_tasks = {}
    
    async def start_auto_renewal(self, secret_path: str, ttl: int = 3600):
        """Автоматическое обновление секретов"""
        while True:
            try:
                # Обновляем секрет за 10% до истечения срока
                await asyncio.sleep(ttl * 0.9)
                
                if "dynamic" in secret_path:
                    # Для динамических секретов получаем новые
                    await self.renew_dynamic_secret(secret_path)
                else:
                    # Для статических - проверяем актуальность
                    await self.check_secret_freshness(secret_path)
                    
            except Exception as e:
                print(f"Ошибка обновления {secret_path}: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут перед повторной попыткой
    
    async def renew_dynamic_secret(self, path: str):
        """Обновление динамических учетных данных"""
        # Логика для различных типов динамических секретов
        if path.startswith("database/creds"):
            # База данных - получаем новые учетные данные
            new_creds = self.get_database_creds(path)
            await self.notify_agents(path, new_creds)
```

---

## 📊 6. МОНИТОРИНГ И АУДИТ

### 6.1 Включение аудита

```bash
# Включение аудита в файл
vault audit enable file file_path=/var/log/vault/audit.log

# Включение аудита в syslog
vault audit enable syslog tag="vault" facility="AUTH"

# Просмотр логов аудита
tail -f /var/log/vault/audit.log | jq '.'

# Фильтрация по действиям УАДИА
grep -i "uaia" /var/log/vault/audit.log | jq '.request.path'
```

### 6.2 Метрики и мониторинг

```bash
# Включение метрик
vault operator raft configuration -format=json | jq '.config.metrics'

# Экспорт метрик в Prometheus
cat > /etc/vault.d/vault.hcl << EOF
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = true
}
EOF

# Prometheus конфигурация
scrape_configs:
  - job_name: 'vault'
    static_configs:
      - targets: ['vault.uaia.network:8200']
    metrics_path: '/v1/sys/metrics'
    params:
      format: ['prometheus']
```

### 6.3 Скрипты мониторинга для УАДИА

```bash
#!/bin/bash
# vault-health-monitor.sh

VAULT_ADDR="http://vault.uaia.network:8200"
HEALTH_CHECK=$(curl -s $VAULT_ADDR/v1/sys/health | jq '.')

echo "=== МОНИТОРИнг VAULT ДЛЯ УАДИА ==="
echo "Время: $(date)"
echo ""

# Проверка состояния
if echo $HEALTH_CHECK | jq -e '.initialized == true' > /dev/null; then
  echo "✅ Vault инициализирован"
else
  echo "❌ Vault не инициализирован"
fi

if echo $HEALTH_CHECK | jq -e '.sealed == false' > /dev/null; then
  echo "✅ Vault распечатан"
else
  echo "❌ Vault запечатан"
  # Автоматическая распечатка
  for KEY in $(cat /etc/uaia/vault-unseal-keys.txt | head -3); do
    vault operator unseal $KEY
  done
fi

# Проверка доступности секретов УАДИА
SECRETS_LIST=$(vault kv list uaia/ 2>/dev/null || echo "Ошибка доступа")
echo "Доступные секреты УАДИА:"
echo "$SECRETS_LIST"

# Проверка токенов
TOKEN_INFO=$(vault token lookup -format=json 2>/dev/null)
if [ $? -eq 0 ]; then
  EXPIRY=$(echo $TOKEN_INFO | jq -r '.data.expire_time')
  echo "Токен истекает: $EXPIRY"
else
  echo "⚠️ Проблема с токеном"
fi
```

---

## 🔄 7. РЕЗЕРВНОЕ КОПИРОВАНИЕ И ВОССТАНОВЛЕНИЕ

### 7.1 Резервное копирование Vault

```bash
#!/bin/bash
# vault-backup.sh

BACKUP_DIR="/backup/vault"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vault_backup_$DATE.json"

# Создание снапшота
vault operator raft snapshot save $BACKUP_FILE

# Шифрование резервной копии
gpg --encrypt --recipient "uaia-security@uaia.network" $BACKUP_FILE
rm $BACKUP_FILE  # Удаляем незашифрованную версию

# Загрузка в S3 (через динамические учетные данные)
AWS_CREDS=$(vault read -format=json aws/creds/uaia-backup)
export AWS_ACCESS_KEY_ID=$(echo $AWS_CREDS | jq -r '.data.access_key')
export AWS_SECRET_ACCESS_KEY=$(echo $AWS_CREDS | jq -r '.data.secret_key')

aws s3 cp $BACKUP_FILE.gpg s3://uaia-vault-backups/

echo "Резервная копия создана: $BACKUP_FILE.gpg"
```

### 7.2 Восстановление из резервной копии

```bash
#!/bin/bash
# vault-restore.sh

BACKUP_FILE="$1"
TEMP_RESTORE="/tmp/vault_restore.json"

# Расшифровка
gpg --decrypt $BACKUP_FILE > $TEMP_RESTORE

# Остановка Vault
systemctl stop vault

# Восстановление из снапшота
vault operator raft snapshot restore $TEMP_RESTORE

# Запуск Vault
systemctl start vault

# Распечатка
for KEY in $(cat /etc/uaia/vault-unseal-keys.txt | head -3); do
  vault operator unseal $KEY
done

rm $TEMP_RESTORE
echo "Восстановление завершено"
```

### 7.3 Миграция секретов УАДИА

```python
# migrate_secrets.py
import hvac
import json

def migrate_uaia_secrets(source_vault, target_vault):
    """Миграция всех секретов УАДИА между инстансами Vault"""
    
    # Получение списка всех секретов УАДИА
    secrets_paths = source_vault.secrets.kv.v2.list_secrets("uaia")
    
    for path in secrets_paths['data']['keys']:
        print(f"Миграция: {path}")
        
        # Чтение секрета
        secret = source_vault.secrets.kv.v2.read_secret_version(f"uaia/{path}")
        
        # Запись в целевой Vault
        target_vault.secrets.kv.v2.create_or_update_secret(
            path=f"uaia/{path}",
            secret=secret['data']['data']
        )
    
    print("Миграция завершена!")
```

---

## 🛡️ 8. БЕЗОПАСНОСТЬ ДЛЯ СИСТЕМЫ УАДИА

### 8.1 Шифрование секретов в транзите

```bash
# Генерация ключа шифрования для УАДИА
vault write transit/keys/uaia-encryption-key \
  type="aes256-gcm96" \
  derived=true \
  convergent_encryption=true

# Шифрование секрета перед записью
PLAINTEXT="super-secret-token-for-uaia"
ENCRYPTED=$(vault write -field=ciphertext transit/encrypt/uaia-encryption-key \
  plaintext=$(base64 <<< "$PLAINTEXT"))

# Дешифрование при чтении
DECRYPTED=$(vault write -field=plaintext transit/decrypt/uaia-encryption-key \
  ciphertext="$ENCRYPTED" | base64 --decode)

echo "Расшифровано: $DECRYPTED"
```

### 8.2 Сегментация секретов по окружениям

```bash
# Создание отдельных пространств имен (Namespaces) для окружений
vault namespace create uaia-prod
vault namespace create uaia-staging
vault namespace create uaia-dev

# Работа в конкретном namespace
export VAULT_NAMESPACE="uaia-prod"
vault kv put uaia/architect/api-keys openai="prod-key-123"

export VAULT_NAMESPACE="uaia-dev"
vault kv put uaia/architect/api-keys openai="dev-key-456"
```

### 8.3 Временные токены для агентов

```bash
# Создание политики с ограниченным временем жизни
vault policy write uaia-temp-token - << EOF
path "uaia/data/agents/*" {
  capabilities = ["read"]
  max_wrapping_ttl = "300s"
}
EOF

# Создание временного токена (5 минут)
vault token create -policy="uaia-temp-token" -ttl="5m" -renewable=true

# Обертывание секрета (wrapping)
vault kv put uaia/wrapped/temp-secret value="temporary-secret"
WRAPPED_TOKEN=$(vault kv get -wrap-ttl=120s -field=wrapping_token uaia/wrapped/temp-secret)

# Распаковка секрета агентом
vault unwrap $WRAPPED_TOKEN
```

---

## 🚀 9. АВТОМАТИЗАЦИЯ ДЛЯ УАДИА

### 9.1 Terraform конфигурация

```hcl
# terraform/vault.tf
resource "vault_mount" "uaia_kv" {
  path        = "uaia"
  type        = "kv-v2"
  description = "KV store for UAIA system"
}

resource "vault_policy" "uaia_agent" {
  name = "uaia-agent"
  
  policy = <<EOT
path "uaia/data/agents/{{identity.entity.name}}/*" {
  capabilities = ["read", "list"]
}

path "database/creds/uaia-{{identity.entity.name}}" {
  capabilities = ["read"]
}
EOT
}

resource "vault_approle_auth_backend_role" "uaia_architect" {
  backend   = vault_auth_backend.approle.path
  role_name = "uaia-architect"
  
  token_policies = [vault_policy.uaia_agent.name]
  secret_id_ttl  = "600"
  token_ttl      = "3600"
  token_max_ttl  = "7200"
}
```

### 9.2 CI/CD интеграция

```yaml
# .github/workflows/deploy-uaia.yml
name: Deploy UAIA with Vault Secrets

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout
      uses: actions/checkout@v3
      
    - name: Get Vault Secrets
      env:
        VAULT_ADDR: ${{ secrets.VAULT_ADDR }}
        VAULT_TOKEN: ${{ secrets.VAULT_TOKEN }}
      run: |
        # Получение секретов для развертывания
        TELEGRAM_TOKEN=$(vault kv get -field=telegram_token uaia/data/agents/architect)
        AKASH_MNEMONIC=$(vault kv get -field=akash_mnemonic uaia/data/agents/deploy)
        
        # Создание .env файла
        echo "TELEGRAM_TOKEN=$TELEGRAM_TOKEN" >> .env
        echo "AKASH_MNEMONIC=$AKASH_MNEMONIC" >> .env
        
    - name: Deploy to Akash
      run: |
        # Использование секретов из Vault для развертывания
        source .env
        ./scripts/deploy-to-akash.sh
```

### 9.3 Автоматическое ротирование секретов

```python
# secret_rotation.py
import schedule
import time
from uaia_vault_client import UaiaVaultClient

class UaiaSecretRotator:
    def __init__(self):
        self.vault = UaiaVaultClient()
        
    def rotate_api_keys(self):
        """Ротация API ключей"""
        # Генерация новых ключей
        new_openai_key = self.generate_openai_key()
        new_telegram_token = self.generate_telegram_token()
        
        # Запись в Vault
        self.vault.store_secrets({
            'openai': new_openai_key,
            'telegram': new_telegram_token
        })
        
        # Уведомление агентов
        self.notify_agents_key_rotation()
    
    def schedule_rotations(self):
        """Планирование ротаций"""
        # Ежедневная ротация в 3:00
        schedule.every().day.at("03:00").do(self.rotate_api_keys)
        
        # Ротация БД паролей каждую неделю
        schedule.every().week.do(self.rotate_db_passwords)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
```

---

## 🎯 10. ЛУЧШИЕ ПРАКТИКИ ДЛЯ УАДИА

### 10.1 Чек-лист безопасности

```bash
#!/bin/bash
# vault-security-checklist.sh

echo "=== ПРОВЕРКА БЕЗОПАСНОСТИ VAULT ДЛЯ УАДИА ==="

# 1. Проверка TLS
echo "1. Проверка TLS соединения..."
curl -ks https://vault.uaia.network:8200/v1/sys/health | jq '.'

# 2. Проверка политик
echo "2. Проверка политик доступа..."
vault policy list | grep uaia

# 3. Проверка аудита
echo "3. Проверка включенного аудита..."
vault audit list

# 4. Проверка версии
echo "4. Проверка версии Vault..."
vault version

# 5. Проверка режима
echo "5. Проверка режима работы..."
vault status | grep -E "Sealed|Initialized"

echo "=== ПРОВЕРКА ЗАВЕРШЕНА ==="
```

### 10.2 Рекомендуемая структура для УАДИА

```
uaia/
├── data/
│   ├── agents/
│   │   ├── architect/
│   │   │   ├── core
│   │   │   ├── api-keys
│   │   │   └── config
│   │   ├── infra/
│   │   ├── security/
│   │   └── deploy/
│   ├── external/
│   │   ├── akash/
│   │   ├── telegram/
│   │   └── apis/
│   └── users/
│       ├── admin/
│       └── service-accounts/
├── dynamic/
│   ├── database/
│   │   ├── postgres/
│   │   └── redis/
│   └── cloud/
│       ├── aws/
│       └── akash/
└── transit/
    └── keys/
        └── uaia-encryption
```

### 10.3 Экстренные процедуры

```bash
#!/bin/bash
# vault-emergency.sh

case "$1" in
  "seal")
    # Экстренное запечатывание Vault
    echo "Запечатывание Vault..."
    vault operator seal
    ;;
    
  "revoke-all")
    # Отзыв всех токенов (кроме корневого)
    echo "Отзыв всех токенов..."
    vault token revoke -mode path auth/token/create
    ;;
    
  "disable-auth")
    # Временное отключение методов аутентификации
    echo "Отключение аутентификации..."
    vault auth disable approle
    vault auth disable kubernetes
    ;;
    
  "backup-now")
    # Немедленное резервное копирование
    echo "Создание экстренной резервной копии..."
    vault operator raft snapshot save /backup/emergency-$(date +%s).snap
    ;;
    
  *)
    echo "Использование: $0 {seal|revoke-all|disable-auth|backup-now}"
    ;;
esac
```

---

## ✅ БЫСТРЫЙ СТАРТ ДЛЯ УАДИА

```bash
#!/bin/bash
# quick-start-uaia-vault.sh

echo "=== БЫСТРЫЙ СТАРТ VAULT ДЛЯ УАДИА ==="

# 1. Запуск Vault в dev режиме
vault server -dev -dev-root-token-id="uaia-initial" &
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='uaia-initial'

sleep 2

# 2. Настройка хранилища для УАДИА
vault secrets enable -path=uaia kv-v2

# 3. Создание базовых секретов
vault kv put uaia/quick-start \
  message="Добро пожаловать в УАДИА!" \
  status="active" \
  version="1.0.0"

# 4. Проверка
echo "Секрет создан:"
vault kv get uaia/quick-start

echo "=== ГОТОВО! ==="
echo "Адрес: $VAULT_ADDR"
echo "Токен: $VAULT_TOKEN"
```

---

## 📚 РЕКОМЕНДУЕМЫЕ НАСТРОЙКИ ДЛЯ ПРОДАКШЕНА УАДИА

1. **High Availability**: Настройка кластера из 3+ нод
2. **Auto-unseal**: Использование AWS KMS или GCP KMS для автоматической распечатки
3. **Namespace**: Разделение на uaia-prod, uaia-staging, uaia-dev
4. **Backup**: Ежедневные снапшоты с шифрованием
5. **Monitoring**: Интеграция с Prometheus и Grafana
6. **Access Control**: Строгие политики для каждого агента
7. **Secret Rotation**: Автоматическая ротация каждые 90 дней
8. **Audit Trail**: Подробное логирование всех операций

---

**Готово к использованию!** Эта памятка покрывает все аспекты использования Vault для системы УАДИА — от установки до продвинутых операций. 🚀
