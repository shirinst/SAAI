📜 Памятка по использованию Akash CLI для системы УАДИА

🔧 1. УСТАНОВКА И НАСТРОЙКА

1.1 Установка Akash CLI

```bash
# Для Linux/macOS
curl -sSfL https://raw.githubusercontent.com/akash-network/node/master/install.sh | sh
sudo mv ./bin/akash /usr/local/bin/
akash version  # Проверка установки

# Альтернативный метод (бинарный файл)
wget https://github.com/akash-network/node/releases/download/v0.28.0/akash_0.28.0_linux_amd64.zip
unzip akash_*.zip
sudo mv akash /usr/local/bin/
```

1.2 Настройка окружения

```bash
# Основные переменные окружения
export AKASH_NODE="https://rpc.akashnet.net:443"
export AKASH_CHAIN_ID="akashnet-2"
export AKASH_KEYRING_BACKEND="os"  # или "file", "test"

# Альтернативные ноды (если основная недоступна)
export AKASH_NODE="https://akash-rpc.polkachu.com:443"
# или
export AKASH_NODE="https://rpc.akash.forbole.com:443"
```

1.3 Проверка подключения

```bash
# Проверка состояния сети
akash status

# Проверка синхронизации ноды
akash status 2>&1 | jq '.SyncInfo.catching_up'

# Получение информации о сети
akash query staking params
```

---

💼 2. УПРАВЛЕНИЕ КОШЕЛЬКОМ И ФИНАНСАМИ

2.1 Создание и управление кошельками

```bash
# Создание нового кошелька (запомните мнемоническую фразу!)
akash keys add uaia-wallet --keyring-backend os

# Восстановление кошелька из seed-фразы
akash keys add uaia-wallet-recovery --recover --keyring-backend os

# Просмотр списка кошельков
akash keys list --keyring-backend os

# Экспорт кошелька
akash keys export uaia-wallet --keyring-backend os

# Удаление кошелька (осторожно!)
akash keys delete uaia-wallet --keyring-backend os
```

2.2 Получение информации о балансе

```bash
# Получение адреса кошелька
AKASH_ACCOUNT_ADDRESS=$(akash keys show uaia-wallet -a --keyring-backend os)
echo $AKASH_ACCOUNT_ADDRESS

# Проверка баланса
akash query bank balances $AKASH_ACCOUNT_ADDRESS

# Проверка только AKT
akash query bank balances $AKASH_ACCOUNT_ADDRESS --output json | jq '.balances[] | select(.denom=="uakt") | .amount'

# Конвертация uakt → AKT
akt_balance=$(akash query bank balances $AKASH_ACCOUNT_ADDRESS --output json | jq '.balances[] | select(.denom=="uakt") | .amount')
echo "AKT баланс: $(echo "$akt_balance / 1000000" | bc).$(echo "$akt_balance % 1000000" | bc)"
```

2.3 Пополнение счета и транзакции

```bash
# Пример депозита (с биржи на кошелек)
# AKASH_ACCOUNT_ADDRESS = ваш адрес akash1...

# Перевод между кошельками
akash tx bank send uaia-wallet akash1destinationaddress 1000000uakt \
  --chain-id $AKASH_CHAIN_ID \
  --keyring-backend os \
  --node $AKASH_NODE

# Проверка транзакции по хэшу
akash query tx <TX_HASH> --node $AKASH_NODE
```

---

🚀 3. РАЗВЕРТЫВАНИЕ ПРИЛОЖЕНИЙ

3.1 Создание файла развертывания (deploy.yml)

```yaml
# uaia-architect-deploy.yml
version: "2.0"

services:
  uaia-architect:
    image: ghcr.io/your-org/uaia-architect:latest
    env:
      - NODE_ENV=production
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
      - VAULT_ADDR=${VAULT_ADDR}
    expose:
      - port: 3000
        as: 80
        to:
          - global: true
        accept:
          - uaia-architect.yourdomain.network
        proto: http

profiles:
  compute:
    uaia-architect:
      resources:
        cpu:
          units: 1.0
        memory:
          size: 2Gi
        storage:
          size: 10Gi
        gpu:
          units: 0  # Для агентов с ML можно указать GPU

  placement:
    akash:
      pricing:
        uaia-architect:
          denom: uakt
          amount: 1000  # Цена за блок (~6 секунд)

deployment:
  uaia-architect:
    akash:
      profile: uaia-architect
      count: 1
```

3.2 Процесс развертывания

```bash
# 1. Создание сертификата для развертывания
akash tx cert create client --chain-id $AKASH_CHAIN_ID \
  --keyring-backend os \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE \
  --fees 5000uakt

# Проверка сертификата
akash query cert list --owner $AKASH_ACCOUNT_ADDRESS

# 2. Отправка манифеста развертывания
akash tx deployment create uaia-architect-deploy.yml \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE \
  --chain-id $AKASH_CHAIN_ID \
  --fees 5000uakt

# 3. Получение списка развертываний
akash query deployment list --owner $AKASH_ACCOUNT_ADDRESS

# 4. Просмотр биддов (предложений от провайдеров)
akash query market bid list --owner $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE \
  --state open

# 5. Выбор лучшего бидда
BID_ID="<bid-sequence-from-list>"
akash tx market lease create --bid $BID_ID \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE \
  --chain-id $AKASH_CHAIN_ID
```

3.3 Обновление и управление развертываниями

```bash
# Обновление существующего развертывания
akash tx deployment update <DSEQ> uaia-architect-deploy-v2.yml \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE

# Закрытие развертывания
akash tx deployment close --dseq <DSEQ> \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE

# Просмотр активных лизингов
akash query market lease list --owner $AKASH_ACCOUNT_ADDRESS
```

---

🌐 4. УПРАВЛЕНИЕ ДОМЕНАМИ И SSL

4.1 Настройка пользовательского домена

```bash
# 1. Получение информации о развертывании
akash provider lease-status \
  --dseq <DSEQ> \
  --provider <PROVIDER_ADDRESS> \
  --node $AKASH_NODE \
  --from $AKASH_ACCOUNT_ADDRESS

# 2. Настройка CNAME записи в DNS
# Полученные данные:
# - Внешний порт и хостнейм провайдера
# Пример: abc123.ingress.provider.akash.network

# 3. Обновление манифеста с пользовательским доменом
# В секции expose добавить:
# accept:
#   - uaia-architect.yourdomain.network
```

4.2 Автоматическое обновление DNS через скрипт

```bash
#!/bin/bash
# update-dns.sh
DEPLOYMENT_DSEQ=$1
DOMAIN_NAME="uaia-architect.yourdomain.network"

# Получение текущего хоста от провайдера
LEASE_INFO=$(akash provider lease-status \
  --dseq $DEPLOYMENT_DSEQ \
  --provider $(akash query market lease list --owner $AKASH_ACCOUNT_ADDRESS | jq -r '.leases[0].lease.lease_id.provider') \
  --node $AKASH_NODE \
  --from $AKASH_ACCOUNT_ADDRESS --output json)

HOSTNAME=$(echo $LEASE_INFO | jq -r '.services[] | select(.name=="uaia-architect") | .uris[0]')

# Обновление DNS через Cloudflare API
curl -X PATCH "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/dns_records/YOUR_RECORD_ID" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"content\":\"$HOSTNAME\",\"type\":\"CNAME\",\"name\":\"$DOMAIN_NAME\",\"ttl\":120}"
```

4.3 Управление SSL сертификатами

```bash
# Генерация SSL сертификата для домена
akash tx cert create server uaia-architect.yourdomain.network \
  --chain-id $AKASH_CHAIN_ID \
  --keyring-backend os \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE \
  --fees 5000uakt

# Проверка SSL сертификатов
akash query cert list --owner $AKASH_ACCOUNT_ADDRESS

# Обновление SSL сертификата (перед истечением срока)
akash tx cert renew server uaia-architect.yourdomain.network \
  --chain-id $AKASH_CHAIN_ID \
  --keyring-backend os \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE

# Отзыв сертификата
akash tx cert revoke server uaia-architect.yourdomain.network \
  --chain-id $AKASH_CHAIN_ID \
  --keyring-backend os \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE
```

---

🔍 5. МОНИТОРИНГ И ДИАГНОСТИКА

5.1 Команды для мониторинга

```bash
# Проверка статуса развертывания
akash provider lease-status \
  --dseq <DSEQ> \
  --provider <PROVIDER_ADDRESS> \
  --node $AKASH_NODE \
  --from $AKASH_ACCOUNT_ADDRESS

# Логи развертывания
akash provider lease-logs \
  --dseq <DSEQ> \
  --provider <PROVIDER_ADDRESS> \
  --node $AKASH_NODE \
  --from $AKASH_ACCOUNT_ADDRESS \
  --service uaia-architect

# SSH доступ в контейнер (если настроен)
akash provider lease-shell \
  --dseq <DSEQ> \
  --provider <PROVIDER_ADDRESS> \
  --node $AKASH_NODE \
  --from $AKASH_ACCOUNT_ADDRESS

# Проверка событий развертывания
akash query tx --events "message.sender='$AKASH_ACCOUNT_ADDRESS'" --limit 50
```

5.2 Скрипт для автоматического мониторинга

```bash
#!/bin/bash
# monitor-deployments.sh

# Проверка баланса
BALANCE=$(akash query bank balances $AKASH_ACCOUNT_ADDRESS --output json | jq '.balances[] | select(.denom=="uakt") | .amount')
if [ $(echo "$BALANCE < 1000000" | bc) -eq 1 ]; then
  echo "ВНИМАНИЕ: Низкий баланс! Текущий: $(echo "$BALANCE / 1000000" | bc) AKT"
fi

# Проверка активных развертываний
ACTIVE_DEPLOYMENTS=$(akash query deployment list --owner $AKASH_ACCOUNT_ADDRESS --state active | jq '.deployments | length')
echo "Активных развертываний: $ACTIVE_DEPLOYMENTS"

# Проверка сертификатов
CERT_EXPIRY=$(akash query cert list --owner $AKASH_ACCOUNT_ADDRESS --output json | jq '.certificates[0].certificate.cert')
if [ "$CERT_EXPIRY" != "null" ]; then
  echo "Сертификаты активны"
else
  echo "ВНИМАНИЕ: Нет активных сертификатов!"
fi
```

---

⚙️ 6. ПРОДВИНУТЫЕ ОПЕРАЦИИ

6.1 Управление несколькими развертываниями

```bash
# Пакетное развертывание агентов УАДИА
for AGENT in architect infra security deploy monitor code db; do
  echo "Развертывание $AGENT агента..."
  
  # Генерация манифеста для каждого агента
  cat > deploy-$AGENT.yml << EOF
version: "2.0"
services:
  uaia-$AGENT:
    image: ghcr.io/your-org/uaia-$AGENT:latest
    env:
      - AGENT_NAME=$AGENT
      - ROLE=${AGENT^^}
    expose:
      - port: 3000
        as: 80
        to:
          - global: true
        accept:
          - uaia-$AGENT.yourdomain.network
profiles:
  compute:
    uaia-$AGENT:
      resources:
        cpu:
          units: 0.5
        memory:
          size: 1Gi
        storage:
          size: 5Gi
  placement:
    akash:
      pricing:
        uaia-$AGENT:
          denom: uakt
          amount: 500
EOF
  
  # Развертывание
  akash tx deployment create deploy-$AGENT.yml \
    --from $AKASH_ACCOUNT_ADDRESS \
    --node $AKASH_NODE \
    --chain-id $AKASH_CHAIN_ID \
    --fees 5000uakt
  
  sleep 10  # Пауза между развертываниями
done
```

6.2 Автоматизация с помощью скриптов

```bash
#!/bin/bash
# deploy-uaia-system.sh
# Полная автоматизация развертывания системы УАДИА

set -e  # Прекратить выполнение при ошибке

# Конфигурация
DEPLOYMENT_MANIFEST="uaia-full-system.yml"
MIN_BALANCE=5000000  # 5 AKT в uakt

# Проверка баланса
check_balance() {
  local balance=$(akash query bank balances $AKASH_ACCOUNT_ADDRESS --output json | jq '.balances[] | select(.denom=="uakt") | .amount')
  
  if [ -z "$balance" ] || [ "$balance" -lt $MIN_BALANCE ]; then
    echo "ОШИБКА: Недостаточный баланс. Минимум: $MIN_BALANCE uakt"
    exit 1
  fi
  echo "Баланс OK: $balance uakt"
}

# Основной процесс развертывания
main() {
  echo "=== Запуск развертывания системы УАДИА ==="
  
  # Проверки
  check_balance
  
  # Создание/обновление сертификата
  echo "Настройка SSL сертификата..."
  akash tx cert create client --chain-id $AKASH_CHAIN_ID \
    --keyring-backend os \
    --from $AKASH_ACCOUNT_ADDRESS \
    --node $AKASH_NODE \
    --fees 5000uakt -y
  
  # Развертывание
  echo "Отправка манифеста развертывания..."
  DEPLOYMENT_TX=$(akash tx deployment create $DEPLOYMENT_MANIFEST \
    --from $AKASH_ACCOUNT_ADDRESS \
    --node $AKASH_NODE \
    --chain-id $AKASH_CHAIN_ID \
    --fees 5000uakt -y --output json)
  
  DEPLOYMENT_DSEQ=$(echo $DEPLOYMENT_TX | jq -r '.logs[0].events[] | select(.type=="akash.v1") | .attributes[] | select(.key=="dseq") | .value')
  
  echo "Развертывание создано. DSEQ: $DEPLOYMENT_DSEQ"
  
  # Ожидание биддов
  echo "Ожидание предложений от провайдеров..."
  sleep 30
  
  # Выбор лучшего бидда
  select_best_bid $DEPLOYMENT_DSEQ
}

# Функция выбора лучшего бидда
select_best_bid() {
  local dseq=$1
  
  # Получение списка биддов
  BIDS=$(akash query market bid list --owner $AKASH_ACCOUNT_ADDRESS \
    --node $AKASH_NODE \
    --dseq $dseq \
    --state open --output json)
  
  # Выбор бидда с минимальной ценой
  BEST_BID=$(echo $BIDS | jq -r '.bids | sort_by(.bid.price.amount) | .[0].bid.bid_id')
  
  if [ -n "$BEST_BID" ] && [ "$BEST_BID" != "null" ]; then
    echo "Выбор лучшего бидда: $BEST_BID"
    
    # Принятие бидда
    akash tx market lease create --bid $BEST_BID \
      --from $AKASH_ACCOUNT_ADDRESS \
      --node $AKASH_NODE \
      --chain-id $AKASH_CHAIN_ID \
      --fees 5000uakt -y
    
    echo "Развертывание успешно запущено!"
  else
    echo "ОШИБКА: Не получены бидды"
    exit 1
  fi
}

# Запуск
main
```

---

🛠️ 7. УСТРАНЕНИЕ НЕИСПРАВНОСТЕЙ

7.1 Частые проблемы и решения

```bash
# Проблема: "account sequence mismatch"
# Решение: Подождать несколько секунд и повторить
sleep 5
# или сбросить последовательность
akash query account $AKASH_ACCOUNT_ADDRESS

# Проблема: Недостаточно средств для комиссии
# Решение: Пополнить баланс
echo "Минимальный рекомендуемый баланс: 0.5 AKT (500000 uakt)"

# Проблема: Нет доступных провайдеров
# Решение: Проверить доступность сети
akash status
# Или попробовать другой манифест с меньшими требованиями

# Проблема: Ошибка образа Docker
# Решение: Проверить доступность образа и теги
docker pull ghcr.io/your-org/uaia-architect:latest
```

7.2 Полезные команды для отладки

```bash
# Проверка состояния сети
akash status --node $AKASH_NODE

# Поиск провайдеров с доступными ресурсами
akash query provider list --node $AKASH_NODE

# Детальная информация о провайдере
akash query provider get <PROVIDER_ADDRESS> --node $AKASH_NODE

# Проверка событий в реальном времени
akash query txs --events "message.module='deployment'" --limit 20

# Очистка кэша CLI
rm -rf ~/.akash/
```

---

📚 8. ЛУЧШИЕ ПРАКТИКИ ДЛЯ СИСТЕМЫ УАДИА

8.1 Рекомендации по безопасности

```bash
# 1. Использовать разные кошельки для разных окружений
# Разработка
export AKASH_ACCOUNT_ADDRESS_DEV=$(akash keys show uaia-dev -a)
# Продакшн
export AKASH_ACCOUNT_ADDRESS_PROD=$(akash keys show uaia-prod -a)

# 2. Регулярная ротация сертификатов
# Добавить в crontab:
# 0 0 1 * * /path/to/renew-certificates.sh

# 3. Мониторинг расходов
# Скрипт для отслеживания расходов по развертываниям
```

8.2 Оптимизация стоимости

```bash
# 1. Использование spot pricing
# В манифесте указывать минимальную цену:
# pricing:
#   uaia-architect:
#     denom: uakt
#     amount: 100  # Начинать с низкой цены

# 2. Автоматическое масштабирование
# Скрипт для мониторинга нагрузки и создания/закрытия развертываний

# 3. Использование более дешевых регионов
# Фильтрация провайдеров по региону в манифесте
```

8.3 Интеграция с CI/CD УАДИА

```yaml
# .github/workflows/deploy-to-akash.yml
name: Deploy to Akash

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Akash CLI
      run: |
        curl -sSfL https://raw.githubusercontent.com/akash-network/node/master/install.sh | sh
        sudo mv ./bin/akash /usr/local/bin/
    
    - name: Deploy to Akash
      env:
        AKASH_NODE: ${{ secrets.AKASH_NODE }}
        AKASH_CHAIN_ID: ${{ secrets.AKASH_CHAIN_ID }}
        AKASH_ACCOUNT_ADDRESS: ${{ secrets.AKASH_ACCOUNT_ADDRESS }}
        MNEMONIC: ${{ secrets.MNEMONIC }}
      run: |
        # Восстановление кошелька из секрета
        echo "$MNEMONIC" | akash keys add uaia-deployer --recover --keyring-backend file
        
        # Развертывание
        ./scripts/deploy-uaia-system.sh
```

---

🎯 БЫСТРЫЙ СТАРТ ДЛЯ АГЕНТОВ УАДИА

Минимальный рабочий скрипт

```bash
#!/bin/bash
# quick-deploy.sh - Быстрое развертывание агента

# Конфигурация
AGENT_NAME=$1
IMAGE_TAG=$2
MEMORY="1Gi"
CPU="0.5"

# Создание минимального манифеста
cat > deploy-$AGENT_NAME.yml << EOF
version: "2.0"
services:
  $AGENT_NAME:
    image: ghcr.io/your-org/$AGENT_NAME:$IMAGE_TAG
    expose:
      - port: 3000
        as: 80
        to:
          - global: true
profiles:
  compute:
    $AGENT_NAME:
      resources:
        cpu:
          units: $CPU
        memory:
          size: $MEMORY
  placement:
    akash:
      pricing:
        $AGENT_NAME:
          denom: uakt
          amount: 500
EOF

# Развертывание
akash tx deployment create deploy-$AGENT_NAME.yml \
  --from $AKASH_ACCOUNT_ADDRESS \
  --node $AKASH_NODE \
  --chain-id $AKASH_CHAIN_ID \
  --fees 5000uakt -y

echo "Агент $AGENT_NAME отправлен на развертывание!"
```

---

📈 МОНИТОРИНГ РАСХОДОВ

Скрипт для отслеживания затрат

```bash
#!/bin/bash
# cost-tracker.sh

echo "=== ОТЧЕТ ПО РАСХОДАМ УАДИА ==="
echo "Дата: $(date)"
echo ""

# Текущий баланс
BALANCE=$(akash query bank balances $AKASH_ACCOUNT_ADDRESS --output json | jq '.balances[] | select(.denom=="uakt") | .amount')
echo "Текущий баланс: $(echo "scale=6; $BALANCE/1000000" | bc) AKT"

# Активные развертывания
echo ""
echo "Активные развертывания:"
akash query deployment list --owner $AKASH_ACCOUNT_ADDRESS --state active --output json | \
  jq -r '.deployments[] | "  - \(.deployment.deployment_id.dseq): \(.deployment.state)"'

# Расчет суточных расходов
echo ""
echo "Примерные суточные расходы:"
# Предположим 1000 uakt за блок на развертывание * 14400 блоков в день
DAILY_COST_PER_DEPLOYMENT=$((1000 * 14400))
echo "  На одно развертывание: $(echo "scale=6; $DAILY_COST_PER_DEPLOYMENT/1000000" | bc) AKT/день"
```

---

✅ ЧЕК-ЛИСТ ПЕРЕД РАЗВЕРТЫВАНИЕМ

1. Баланс: Минимум 0.5 AKT на кошельке
2. Сертификат: Активный клиентский сертификат
3. Манифест: Проверенный deploy.yml файл
4. Образ Docker: Доступен публично или через credentials
5. Переменные окружения: Заполнены все необходимые
6. Порты: Корректно указаны в секции expose
7. Ресурсы: Адекватные требования CPU/memory
8. Цена: Конкурентная цена в uakt
9. Резервный баланс: Дополнительные AKT для комиссий

---

Готово к использованию! Эта памятка покрывает 95% операций для управления УАДИА на Akash Network. Для начала рекомендую:

1. Установить CLI и создать кошелек
2. Пополнить баланс (стартово 2-3 AKT)
3. Протестировать развертывание простого контейнера (nginx)
4. Постепенно мигрировать агентов УАДИА

Для автоматизации всего процесса предлагаю разработать Ansible playbook или Terraform модуль для Akash.