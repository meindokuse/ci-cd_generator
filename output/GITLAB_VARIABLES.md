# GitLab CI/CD Variables

## Требуемые переменные окружения

Добавьте следующие переменные в GitLab:

**Путь:** `Settings → CI/CD → Variables`

### ⚙️ Конфигурация

| Variable | Type | Protected | Masked | Example |
|----------|------|-----------|--------|----------|
| `ENV` | Variable | ❌ | ❌ | `dev` |

### 🗄️ База данных

| Variable | Type | Protected | Masked | Example |
|----------|------|-----------|--------|----------|
| `DB_HOST` | Variable | ❌ | ❌ | `postgres_container` |
| `DB_PORT` | Variable | ❌ | ❌ | `5432` |
| `DB_USER` | Variable | ❌ | ❌ | `order_user` |
| `DB_NAME` | Variable | ❌ | ❌ | `order_db` |
| `POSTGRES_USER` | Variable | ❌ | ❌ | `order_user` |
| `POSTGRES_DB` | Variable | ❌ | ❌ | `order_db` |

### 📋 Общие

| Variable | Type | Protected | Masked | Example |
|----------|------|-----------|--------|----------|
| `KAFKA_BROKERS` | Variable | ❌ | ❌ | `kafka:9092` |
| `KAFKA_TOPIC` | Variable | ❌ | ❌ | `orders` |
| `KAFKA_GROUP` | Variable | ❌ | ❌ | `order-service` |
| `HTTP_ADDR` | Variable | ❌ | ❌ | `:8080` |

### 🔒 Секреты

| Variable | Type | Protected | Masked | Example |
|----------|------|-----------|--------|----------|
| `DB_PASSWORD` | Variable | ✅ | ✅ | `<SET_YOUR_VALUE>` |
| `POSTGRES_PASSWORD` | Variable | ✅ | ✅ | `<SET_YOUR_VALUE>` |

---

## Как добавить переменные в GitLab

1. Откройте ваш проект в GitLab
2. Перейдите: **Settings → CI/CD**
3. Разверните секцию **Variables**
4. Нажмите **Add variable**
5. Заполните:
   - **Key**: Имя переменной (например, `DATABASE_URL`)
   - **Value**: Значение переменной
   - **Type**: `Variable`
   - **Protect variable**: ✅ для чувствительных данных
   - **Mask variable**: ✅ для секретов (они не будут видны в логах)
6. Нажмите **Add variable**

