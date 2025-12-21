# План рефакторинга FootageHub

## Принципы
- **Постепенность**: по одному изменению за раз
- **Тестирование**: проверка работоспособности после каждого шага
- **Обратная совместимость**: старый код продолжает работать
- **Безопасность**: не удаляем ничего без 100% уверенности

---

## Фаза 1: Безопасная очистка (низкий риск)

### Шаг 1.1: Удаление явно неиспользуемых утилит (РИСК: МИНИМАЛЬНЫЙ) ✅
**Цель**: Очистить от debug-скриптов

**Файлы для удаления:**
- [x] `/envato_utils/expired_cookies.py` (35 строк) - утилита для отладки, не импортируется
- [x] `/freepik_utils/expired_cookies.py` (35 строк) - утилита для отладки, не импортируется
- [x] `/test.py` (33 строки) - счётчик строк кода

**Проверка перед удалением:**
```bash
# Убедиться, что файлы не импортируются
grep -r "expired_cookies" --exclude-dir=.git --exclude="*.pyc"
grep -r "from test import" --exclude-dir=.git --exclude="*.pyc"
```

**Тестирование после:**
```bash
python main.py  # Проверить запуск бота
```

---

### Шаг 1.2: Переименование файлов с опечатками (РИСК: НИЗКИЙ) ✅
**Цель**: Исправить опечатки в именах

**Действия:**
- [x] Переименовать `/envato_utils/cookue_save_v2.py` → `cookie_saver_v2.py`

**Команды:**
```bash
cd envato_utils
git mv cookue_save_v2.py cookie_saver_v2.py
```

**Проверка:**
```bash
grep -r "cookue_save_v2" --exclude-dir=.git
```

---

### Шаг 1.3: Удаление TODO-комментариев с хардкодом (РИСК: НИЗКИЙ) ✅
**Цель**: Убрать помеченные к удалению константы

**Файлы для изменения:**
1. `/bot/handlers/channel_check.py:16-17` ✅
   ```python
   # УБРАТЬ!!! - перенести в config.py
   CHANNEL_ID = "@footagehub_channel"
   ```

2. `/bot/handlers/admin.py:24-25` ✅
   ```python
   # УБРАТЬ!!! - перенести в config.py
   PRICE_LIST = Path(__file__).resolve().parent / "prices_list.json"
   ```

**План действий:**
- [x] Добавить в `bot/config.py`:
  ```python
  CHANNEL_ID = os.getenv("CHANNEL_ID", "@footagehub_channel")
  CHANNEL_BONUS_CREDITS = int(os.getenv("CHANNEL_BONUS_CREDITS", "2"))
  PRICE_LIST_PATH = Path(__file__).resolve().parent / "handlers" / "prices_list.json"
  ```

- [x] Обновить импорты в файлах:
  ```python
  # bot/handlers/channel_check.py
  from bot.config import CHANNEL_ID, CHANNEL_BONUS_CREDITS

  # bot/handlers/admin.py
  from bot.config import PRICE_LIST_PATH as PRICE_LIST

  # bot/handlers/payment.py
  from bot.config import PRICE_LIST_PATH as PRICE_LIST

  # bot/webhook/webpay.py
  from bot.config import PRICE_LIST_PATH as PRICE_LIST

  # bot/webhook/cryptobot.py
  from bot.config import PRICE_LIST_PATH as PRICE_LIST
  ```

- [x] Удалить локальные определения

**Тестирование:**
```bash
# Проверить что импорты работают
python -c "from bot.config import CHANNEL_ID, PRICE_LIST_PATH; print(CHANNEL_ID, PRICE_LIST_PATH)"
```

---

## Фаза 2: Централизация конфигурации (средний риск)

### Шаг 2.1: Унификация PRICE_LIST (РИСК: СРЕДНИЙ) ✅
**Цель**: Единый источник для путей к prices_list.json

**Проблема**: PRICE_LIST определён в 4 файлах с разными путями

**Решение:**
1. [x] В `bot/config.py` добавить:
   ```python
   from pathlib import Path

   # Пути к файлам конфигурации
   BOT_DIR = Path(__file__).resolve().parent
   HANDLERS_DIR = BOT_DIR / "handlers"
   PRICE_LIST_PATH = HANDLERS_DIR / "prices_list.json"
   ```

2. [x] Обновить файлы:
   - `/bot/handlers/admin.py:25` - заменить на `from bot.config import PRICE_LIST_PATH as PRICE_LIST`
   - `/bot/handlers/payment.py:21` - заменить на `from bot.config import PRICE_LIST_PATH as PRICE_LIST`
   - `/bot/webhook/cryptobot.py:17` - заменить на `from bot.config import PRICE_LIST_PATH as PRICE_LIST`
   - `/bot/webhook/webpay.py:20` - заменить на `from bot.config import PRICE_LIST_PATH as PRICE_LIST`

3. [x] Удалить локальные определения

**Примечание**: Выполнено в рамках Шага 1.3

**Тестирование:**
```bash
# Проверить что файл найден
python -c "from bot.config import PRICE_LIST_PATH; print(PRICE_LIST_PATH.exists())"

# Запустить бота
python main.py
```

---

### Шаг 2.2: Создание utils для загрузки цен (РИСК: НИЗКИЙ)
**Цель**: Убрать дублирование кода чтения JSON

**Создать файл:** `/bot/utils/price_loader.py`
```python
import json
from pathlib import Path
from typing import Dict, Any
from bot.config import PRICE_LIST_PATH

def load_subscription_plans() -> Dict[str, Any]:
    """Загружает конфигурацию подписок из prices_list.json"""
    with open(PRICE_LIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("subscription_plans", {})

def get_plan_config(plan_key: str) -> Dict[str, Any]:
    """Получает конфигурацию конкретного плана"""
    plans = load_subscription_plans()
    return plans.get(plan_key)
```

**Обновить импорты в:**
- `/bot/handlers/payment.py`
- `/bot/webhook/cryptobot.py`
- `/bot/webhook/webpay.py`

**Заменить:**
```python
# Было:
with open(PRICE_LIST, "r", encoding="utf-8") as f:
    data = json.load(f)
plan = data["subscription_plans"].get(plan_key)

# Стало:
from bot.utils.price_loader import get_plan_config
plan = get_plan_config(plan_key)
```

---

### Шаг 2.3: Добавление констант в config.py (РИСК: МИНИМАЛЬНЫЙ) ✅
**Цель**: Убрать магические числа

**Добавить в `bot/config.py`:** ✅
```python
# Лимиты и таймауты
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
BROWSER_RESTART_AFTER = int(os.getenv("BROWSER_RESTART_AFTER", "50"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "300"))

# Бонусы и кредиты
DAILY_FREE_CREDITS = int(os.getenv("DAILY_FREE_CREDITS", "3"))

# Размеры браузера
BROWSER_VIEWPORT_WIDTH = 1920
BROWSER_VIEWPORT_HEIGHT = 1080
```

**Обновить использование в файлах:** ✅
- [x] `/bot/services.py:12` - заменить `asyncio.Semaphore(3)` на `asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)`
- [x] `/envato_utils/test_env.py` - заменить `restart_after=50` на `restart_after=BROWSER_RESTART_AFTER`
- [x] `/bot/schedule_tasks.py:17` - заменить `credits=3` на `credits=DAILY_FREE_CREDITS`
- [x] `/bot/handlers/channel_check.py` - уже использует `CHANNEL_BONUS_CREDITS`

---

## Фаза 3: Объединение дублирующегося кода (средний риск)

### Шаг 3.1: Унификация fix_cookies (РИСК: НИЗКИЙ) ✅
**Цель**: Один модуль для исправления cookies

**Создать:** `/utils/cookie_fixer.py` ✅
```python
import json
import shutil
from pathlib import Path
from typing import List, Dict
from datetime import datetime

def fix_cookies_file(cookie_file: Path, backup: bool = True) -> tuple[int, int]:
    """
    Исправляет формат cookies в файле.

    Args:
        cookie_file: Путь к файлу с cookies
        backup: Создавать ли бэкап

    Returns:
        (fixed_count, total_count)
    """
    if not cookie_file.exists():
        raise FileNotFoundError(f"Cookie file not found: {cookie_file}")

    # Создать бэкап
    if backup:
        backup_file = cookie_file.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(cookie_file, backup_file)
        print(f"Backup created: {backup_file}")

    # Загрузить cookies
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    fixed_count = 0
    for cookie in cookies:
        modified = False

        # Исправить sameSite
        if "sameSite" in cookie and cookie["sameSite"] not in ["Strict", "Lax", "None"]:
            cookie["sameSite"] = "None"
            modified = True

        # Исправить expires
        if "expires" in cookie and cookie["expires"] == -1:
            cookie["expires"] = 253402300799  # 31 Dec 9999
            modified = True

        if modified:
            fixed_count += 1

    # Сохранить
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)

    return fixed_count, len(cookies)
```

**Обновить файлы:** ✅
- [x] `/envato_utils/fix_cookies.py` - заменить на импорт из utils
- [x] `/freepik_utils/fix_cookies.py` - заменить на импорт из utils
- [x] `/utils/cookie_fixer.py` - создан универсальный модуль
- [x] `/utils/__init__.py` - создан

**Реализация:**
- Создан универсальный модуль `utils/cookie_fixer.py` с функциями:
  - `fix_cookies_file()` - исправление cookies с поддержкой backup и output_file
  - `print_cookie_stats()` - вывод статистики
- Оба файла (`envato_utils/fix_cookies.py` и `freepik_utils/fix_cookies.py`) теперь используют общую логику
- Уменьшено дублирование кода с ~150 строк до ~60 строк в каждом файле
- Добавлена улучшенная обработка ошибок

---

## Фаза 4: Разбиение крупных файлов (высокий риск)

### Шаг 4.1: Разделение admin.py (РИСК: ВЫСОКИЙ)
**Цель**: Разбить 736 строк на логические модули

**Структура НОВАЯ:**
```
bot/handlers/admin/
├── __init__.py              # Экспорт всех функций
├── core.py                  # is_admin, show_admin_panel
├── stats.py                 # show_stats, статистика
├── subscriptions.py         # give_subscription_*, create_subscription_for_user
├── database.py              # export_full_db_and_send, restore_db_*
├── broadcast.py             # start_broadcast, send_broadcast_*
├── cookies.py               # upload_cookies
└── roles.py                 # assign_manager_*, assign_partner_*
```

**План миграции:**
1. [ ] Создать директорию `/bot/handlers/admin/`
2. [ ] Создать модули по функциям (начать с `stats.py`)
3. [ ] Переместить функции в соответствующие модули
4. [ ] Создать `__init__.py` с экспортами
5. [ ] Обновить импорты в `main.py`
6. [ ] Удалить старый `admin.py` только после проверки

**Пример `__init__.py`:**
```python
from .core import is_admin, show_admin_panel, admin_router
from .stats import show_stats
from .subscriptions import give_subscription_start, create_subscription_for_user
from .database import export_full_db_and_send, restore_db_start
from .broadcast import start_broadcast
from .cookies import upload_cookies
from .roles import assign_manager_start, assign_partner_start

__all__ = [
    "is_admin",
    "show_admin_panel",
    "admin_router",
    "show_stats",
    # ... и т.д.
]
```

**Тестирование:**
```bash
# Проверить импорты
python -c "from bot.handlers.admin import is_admin, show_admin_panel"

# Запустить бота
python main.py

# Проверить /admin команду
```

---

### Шаг 4.2: Рефакторинг download.py (РИСК: СРЕДНИЙ)
**Цель**: Разделить логику Envato и Freepik

**Структура НОВАЯ:**
```
bot/handlers/download/
├── __init__.py
├── core.py                  # Общие функции, download_router
├── envato.py                # start_download_envato, process_envato_link
├── freepik.py               # start_download_freepik, process_freepik_link
└── validators.py            # Проверка URL, лимитов
```

**План:**
1. [ ] Создать директорию `/bot/handlers/download/`
2. [ ] Переместить Envato-функции в `envato.py`
3. [ ] Переместить Freepik-функции в `freepik.py`
4. [ ] Общие утилиты в `validators.py`
5. [ ] Создать `__init__.py`
6. [ ] Обновить импорты

---

## Фаза 5: Улучшение качества кода (низкий риск)

### Шаг 5.1: Замена bare except (РИСК: НИЗКИЙ)
**Цель**: Специфичная обработка исключений

**Файлы для исправления:**
- [ ] `/envato_utils/envato_playwright.py` (7 мест)
- [ ] `/freepik_utils/freepik.py` (3 места)
- [ ] `/motion_utils/motion.py` (3 места)

**Паттерн замены:**
```python
# Было:
try:
    await page.click(selector)
except:
    pass

# Стало:
try:
    await page.click(selector)
except (TimeoutError, Exception) as e:
    logger.warning(f"Failed to click {selector}: {e}")
```

---

### Шаг 5.2: Замена print() на logger (РИСК: МИНИМАЛЬНЫЙ)
**Цель**: Унифицировать логирование

**Файлы с большим количеством print():**
- `/bot/handlers/channel_check.py` (13 print)
- `/bot/handlers/download.py` (множество)

**Паттерн замены:**
```python
# Было:
print(f"[DEBUG] Processing link: {url}")

# Стало:
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Processing link: {url}")
```

---

## Фаза 6: Очистка test/ директории (низкий риск)

### Шаг 6.1: Организация тестов (РИСК: МИНИМАЛЬНЫЙ)
**Цель**: Структурировать тестовые скрипты

**Новая структура:**
```
test/
├── integration/             # Интеграционные тесты
│   ├── test_envato.py
│   ├── test_freepik.py
│   └── test_webpay.py
├── utils/                   # Утилиты для тестов
│   ├── get_webpay_token.py
│   └── convert_cookies.py
└── deprecated/              # Старые тесты (не удалять сразу)
    └── filesta/
```

---

## Чеклист перед каждым шагом

- [ ] Создать git коммит текущего состояния
- [ ] Прочитать файлы которые будут изменены
- [ ] Проверить что нет зависимостей `grep -r "имя_файла"`
- [ ] Сделать изменения
- [ ] Запустить `python main.py` и проверить отсутствие ошибок импорта
- [ ] Проверить базовую функциональность (команды бота)
- [ ] Создать коммит с описанием изменений

---

## Метрики успеха

### После Фазы 1:
- Удалено 3+ неиспользуемых файла
- Исправлены опечатки в именах
- Убраны TODO-комментарии

### После Фазы 2:
- Все пути к PRICE_LIST централизованы
- Создан модуль price_loader
- Добавлены константы в config.py

### После Фазы 3:
- Один модуль для fix_cookies
- Дублирующийся код удалён

### После Фазы 4:
- admin.py разбит на <200 строк каждый модуль
- download.py разделён на Envato/Freepik

### После Фазы 5:
- 0 bare except в критических местах
- Меньше 50 print() в коде (только debug скрипты)

### После Фазы 6:
- test/ директория организована
- Deprecated код перемещён в отдельную папку

---

## Риски и митигация

| Риск | Вероятность | Воздействие | Митигация |
|------|-------------|-------------|-----------|
| Сломанные импорты | Средняя | Критическое | Git коммиты перед каждым шагом |
| Потеря функциональности | Низкая | Критическое | Тестирование после каждого изменения |
| Конфликты при слиянии | Низкая | Среднее | Работать в отдельной ветке |
| Удаление нужного кода | Очень низкая | Критическое | Переносить в deprecated/, не удалять сразу |

---

## Рекомендуемый порядок выполнения

1. **Неделя 1**: Фаза 1 (безопасная очистка)
2. **Неделя 2**: Фаза 2 (централизация конфигурации)
3. **Неделя 3**: Фаза 3 (объединение дублирующегося кода)
4. **Неделя 4**: Фаза 5 (улучшение качества кода)
5. **Неделя 5**: Фаза 4.1 (разделение admin.py) - КРИТИЧЕСКИЙ ШАГ
6. **Неделя 6**: Фаза 4.2 (рефакторинг download.py)
7. **Неделя 7**: Фаза 6 (организация тестов)

---

## Следующие шаги

После завершения этого плана:
- [ ] Добавить type hints (mypy)
- [ ] Написать unit тесты (pytest)
- [ ] Добавить pre-commit hooks (black, flake8)
- [ ] Документация для каждого модуля (docstrings)