from secretsharing import SecretSharer
from typing import List, Dict, Optional, Tuple
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

class UaiaShamirSecretManager:
    """
    Управление мастер-ключом УАДИА через пороговую схему Шамира.
    Разделяет сид-фразу между агентами и восстанавливает её.
    """
    
    def __init__(self, k: int = 2, n: int = 3):
        """
        Args:
            k: Порог восстановления (сколько долей нужно)
            n: Общее количество долей (сколько агентов)
        """
        self.k = k  # Минимум агентов для восстановления
        self.n = n  # Всего агентов в системе
        
    def split_master_seed(
        self, 
        seed_phrase: str, 
        agent_names: List[str]
    ) -> Dict[str, str]:
        """
        Делит мастер-сид фразу на доли для агентов.
        
        Args:
            seed_phrase: Полная сид-фраза УАДИА (24 слова)
            agent_names: Список имен агентов (длина должна быть >= n)
            
        Returns:
            Словарь {agent_name: shamir_share}
            
        Example:
            >>> manager = UaiaShamirSecretManager(k=2, n=3)
            >>> shares = manager.split_master_seed(
            ...     "word1 word2 ... word24",
            ...     ["architect", "infra", "security"]
            ... )
            >>> print(shares["architect"])  # "1-ab23cd45..."
        """
        if len(agent_names) < self.n:
            raise ValueError(f"Нужно минимум {self.n} агента, передано {len(agent_names)}")
        
        # SSS работает с hex, преобразуем сид-фразу
        seed_hex = seed_phrase.encode().hex()
        
        # Делим секрет
        shares = SecretSharer.split_secret(seed_hex, self.k, self.n)
        
        # Распределяем доли по агентам
        agent_shares = {}
        for i, agent in enumerate(agent_names[:self.n]):
            agent_shares[agent] = shares[i]
            
        # Добавляем метаданные для проверки
        metadata = {
            "k": self.k,
            "n": self.n,
            "agent_order": agent_names[:self.n],
            "checksum": self._create_checksum(seed_phrase)
        }
        
        # Сохраняем метаданные (только для информации)
        with open("uaia_shamir_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Мастер-ключ разделен на {self.n} доли, порог: {self.k}")
        print(f"📋 Метаданные сохранены в uaia_shamir_metadata.json")
        
        return agent_shares
    
    def recover_master_seed(
        self, 
        agent_shares: Dict[str, str]
    ) -> Optional[str]:
        """
        Восстанавливает мастер-сид фразу из долей агентов.
        
        Args:
            agent_shares: Словарь {agent_name: shamir_share}
            
        Returns:
            Восстановленная сид-фраза или None при ошибке
            
        Example:
            >>> manager = UaiaShamirSecretManager(k=2, n=3)
            >>> seed = manager.recover_master_seed({
            ...     "architect": "1-ab23cd45...",
            ...     "infra": "2-cd67ef89..."
            ... })
        """
        try:
            # Проверяем, что достаточно долей
            if len(agent_shares) < self.k:
                print(f"❌ Недостаточно долей: нужно {self.k}, получено {len(agent_shares)}")
                return None
            
            # Извлекаем доли в правильном формате
            shares_list = list(agent_shares.values())
            
            # Восстанавливаем hex-строку
            seed_hex = SecretSharer.recover_secret(shares_list[:self.k])
            
            # Преобразуем hex обратно в сид-фразу
            seed_phrase = bytes.fromhex(seed_hex).decode()
            
            # Проверяем целостность
            if self._validate_seed(seed_phrase):
                print(f"✅ Мастер-ключ успешно восстановлен из {len(agent_shares)} долей")
                return seed_phrase
            else:
                print("❌ Восстановленная сид-фраза не прошла проверку")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка восстановления: {e}")
            return None
    
    def create_agent_key_package(
        self,
        agent_name: str,
        agent_share: str,
        personal_password: str
    ) -> Dict:
        """
        Создает зашифрованный пакет для агента с его долей.
        Агент сможет расшифровать его только своим паролем.
        
        Args:
            agent_name: Имя агента (architect, infra, etc.)
            agent_share: Доля Shamir (например, "1-ab23cd45...")
            personal_password: Персональный пароль агента
            
        Returns:
            Зашифрованный пакет данных для агента
        """
        # Создаем ключ из пароля агента
        salt = f"uaia_agent_{agent_name}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        agent_key = base64.urlsafe_b64encode(
            kdf.derive(personal_password.encode())
        )
        
        # Подготавливаем данные для агента
        agent_data = {
            "agent": agent_name,
            "share": agent_share,
            "k": self.k,
            "n": self.n,
            "timestamp": "2024-01-01T00:00:00Z",
            "role": self._get_agent_role(agent_name)
        }
        
        # Шифруем данные паролем агента
        fernet = Fernet(agent_key)
        encrypted_data = fernet.encrypt(
            json.dumps(agent_data).encode()
        )
        
        package = {
            "agent": agent_name,
            "data": base64.urlsafe_b64encode(encrypted_data).decode(),
            "salt": base64.urlsafe_b64encode(salt).decode(),
            "version": "1.0"
        }
        
        print(f"📦 Создан зашифрованный пакет для агента '{agent_name}'")
        return package
    
    def decrypt_agent_package(
        self,
        package: Dict,
        personal_password: str
    ) -> Optional[Dict]:
        """
        Расшифровывает пакет агента с помощью его пароля.
        """
        try:
            # Восстанавливаем ключ из пароля
            salt = base64.urlsafe_b64decode(package["salt"])
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            agent_key = base64.urlsafe_b64encode(
                kdf.derive(personal_password.encode())
            )
            
            # Расшифровываем данные
            fernet = Fernet(agent_key)
            encrypted_bytes = base64.urlsafe_b64decode(package["data"])
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            agent_data = json.loads(decrypted_bytes.decode())
            
            print(f"🔓 Агент '{agent_data['agent']}' расшифровал свою долю")
            return agent_data
            
        except Exception as e:
            print(f"❌ Ошибка расшифровки пакета: {e}")
            return None
    
    def _create_checksum(self, seed_phrase: str) -> str:
        """Создает контрольную сумму для проверки целостности."""
        import hashlib
        return hashlib.sha256(seed_phrase.encode()).hexdigest()[:8]
    
    def _validate_seed(self, seed_phrase: str) -> bool:
        """Проверяет валидность восстановленной сид-фразы."""
        # Простая проверка: сид-фраза должна содержать пробелы и слова
        words = seed_phrase.split()
        return len(words) in [12, 15, 18, 21, 24]  # Стандартные длины
    
    def _get_agent_role(self, agent_name: str) -> str:
        """Определяет роль агента в системе УАДИА."""
        roles = {
            "architect": "Главный архитектор, полный доступ",
            "infra": "Управление инфраструктурой, доступ к серверам",
            "security": "Безопасность, мониторинг, аудит",
            "deploy": "Развертывание приложений",
            "monitor": "Мониторинг и алертинг"
        }
        return roles.get(agent_name, "Агент системы")
