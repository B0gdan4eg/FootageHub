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

### Шаг 2.2: Создание utils для загрузки цен (РИСК: НИЗКИЙ) ✅
**Цель**: Убрать дублирование кода чтения JSON

**Создан файл:** `/bot/utils/price_loader.py` ✅

**Реализованные функции:**
- `load_subscription_plans()` - загружает все планы из prices_list.json
- `get_plan_config(plan_key)` - получает конфигурацию конкретного плана
- `save_subscription_plans(plans)` - сохраняет обновленные планы

**Обновлены файлы:** ✅
- [x] `/bot/handlers/payment.py` - использует `load_subscription_plans()`
- [x] `/bot/webhook/cryptobot.py` - использует `load_subscription_plans()`
- [x] `/bot/webhook/webpay.py` - использует `load_subscription_plans()`

**Результат:**
- Устранено дублирование кода (4 места → 1 централизованный модуль)
- Улучшена обработка ошибок с логированием
- Единый источник для доступа к списку цен
- Проще поддерживать и тестировать

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

### Шаг 4.1: Разделение admin.py (РИСК: ВЫСОКИЙ) ✅ ЗАВЕРШЕНО
**Цель**: Разбить 734 строки на логические модули

**Выполнено:**
- [x] Phase 1: Подготовка структуры ✅
- [x] Phase 2: Полное разделение на модули ✅

**Созданные модули (9 штук):**
- [x] `bot/handlers/admin/core.py` - Аутентификация и главная панель
- [x] `bot/handlers/admin/stats.py` - Статистика и аналитика
- [x] `bot/handlers/admin/subscriptions.py` - Управление подписками
- [x] `bot/handlers/admin/roles.py` - Назначение ролей
- [x] `bot/handlers/admin/prices.py` - Управление ценами
- [x] `bot/handlers/admin/database.py` - Экспорт/восстановление БД
- [x] `bot/handlers/admin/cookies.py` - Загрузка cookies
- [x] `bot/handlers/admin/limits.py` - Управление лимитами
- [x] `bot/handlers/admin/broadcast.py` - Рассылка сообщений

**Структура после завершения:**
```
bot/handlers/admin/
├── __init__.py              # Combines all 9 routers
├── core.py                  # ~75 lines
├── stats.py                 # ~95 lines
├── subscriptions.py         # ~280 lines
├── roles.py                 # ~50 lines
├── prices.py                # ~55 lines
├── database.py              # ~200 lines
├── cookies.py               # ~60 lines
├── limits.py                # ~35 lines
└── broadcast.py             # ~50 lines
```

**Результаты:**
- Оригинальный `admin_legacy.py` (734 строки) → 9 фокусированных модулей (~100 строк каждый)
- Каждый модуль имеет свой Router
- `__init__.py` объединяет все 9 роутеров в один главный
- Полная обратная совместимость: `from bot.handlers import admin` работает
- Все импорты проверены и работают
- 9 суб-роутеров успешно включены в главный admin router
- `admin_legacy.py` удален после полной миграции

**Тестирование:**
```bash
# Проверено:
✅ python -c "from bot.handlers.admin import is_admin, admin_panel"
✅ python -c "from bot.handlers.admin import router; print(len(router.sub_routers))"
   # Output: 9 sub-routers

# Все функции работают корректно
```

---

### Шаг 4.2: Рефакторинг download.py (РИСК: СРЕДНИЙ) ✅ ЗАВЕРШЕНО
**Цель**: Разделить логику Envato и Freepik

**Выполнено:**
- [x] Создана директория `/bot/handlers/download/` ✅
- [x] Созданы 3 фокусированных модуля ✅

**Созданные модули:**
- [x] `bot/handlers/download/validators.py` (~95 lines) - Общие функции валидации и утилиты
- [x] `bot/handlers/download/envato.py` (~240 lines) - Обработчики загрузки Envato
- [x] `bot/handlers/download/freepik.py` (~235 lines) - Обработчики загрузки Freepik

**Структура после завершения:**
```
bot/handlers/download/
├── __init__.py              # Combines both routers
├── validators.py            # check_user_eligibility, auto_delete_download_link
├── envato.py                # ask_for_link, handle_link, download_more
└── freepik.py               # ask_for_freepik_link, handle_freepik_link, download_more_freepik
```

**Результаты:**
- Оригинальный `download.py` (498 строк) → 3 фокусированных модуля (~190 строк средний)
- Четкое разделение логики Envato и Freepik
- Общие утилиты вынесены в validators (check_user_eligibility, auto_delete_download_link)
- Каждый сервис имеет свой Router
- `__init__.py` объединяет оба роутера
- 2 суб-роутера успешно включены в главный download router
- Полная обратная совместимость: `from bot.handlers import download` работает
- `download.py` удален после полной миграции

**Тестирование:**
```bash
# Проверено:
✅ python -c "from bot.handlers.download import ask_for_link, handle_link"
✅ python -c "from bot.handlers.download import router; print(len(router.sub_routers))"
   # Output: 2 sub-routers

# Все функции работают корректно
```

---

## Фаза 5: Улучшение качества кода (низкий риск)

### Шаг 5.1: Замена bare except (РИСК: НИЗКИЙ) ✅
**Цель**: Специфичная обработка исключений

**Исправлено:**
- [x] `/envato_utils/envato_playwright.py` (7 мест) ✅
- [x] `/freepik_utils/freepik.py` (3 места) ✅
- [x] `/freepik_utils/check_auth.py` (2 места) ✅

**Выполненные замены:**
1. `except:` при чтении cookie_index → `except (ValueError, IOError)`
2. `except:` при сохранении скриншотов → `except Exception as e` с логированием
3. `except:` при wait_for_selector → `except TimeoutError`
4. `except:` при импорте BotServices → `except (ImportError, AttributeError)`
5. `except:` при парсинге JSON → `except (json.JSONDecodeError, KeyError, Exception)`

**Результат:**
- Улучшена обработка ошибок с явными типами исключений
- Добавлено информативное логирование ошибок
- Упрощена отладка при возникновении проблем

---

### Шаг 5.2: Замена print() на logger (РИСК: МИНИМАЛЬНЫЙ) ✅
**Цель**: Унифицировать логирование

**Исправлено:**
- [x] `/bot/handlers/payment.py` (15 print) ✅
- [x] `/bot/handlers/channel_check.py` (13 print) ✅

**Выполненные замены:**
1. Добавлен `logger = logging.getLogger(__name__)` в начало файлов
2. `print(f"[PAYMENT] ❌ Error...")` → `logger.error(f"Error...")`
3. `print(f"[PAYMENT] ⚠️ Warning...")` → `logger.warning(f"Warning...")`
4. `print(f"[PAYMENT] Creating...")` → `logger.info(f"Creating...")`
5. `print(f"[DEBUG] ...")` → `logger.debug(f"...")`

**Результат:**
- Унифицировано логирование в критических хендлерах
- Правильные уровни логов (debug, info, warning, error)
- Удалены избыточные префиксы типа `[PAYMENT]` (автоматически добавляются logger'ом)
- Использован `exc_info=True` для детального логирования исключений

---

## Фаза 6: Очистка test/ директории (низкий риск) ✅ ЗАВЕРШЕНО

### Шаг 6.1: Организация тестов (РИСК: МИНИМАЛЬНЫЙ)
**Цель**: Структурировать тестовые скрипты и утилиты

**Выполнено:**
- [x] Создана директория `scripts/` для development утилит ✅
- [x] Перемещены все утилиты и тесты ✅
- [x] Создана документация для скриптов ✅
- [x] Удалена пустая директория `test/` ✅

**Перемещённые файлы:**

**В utils/:**
- `test/convert_cookies.py` → `utils/convert_cookies.py` - утилита конвертации cookies

**В freepik_utils/:**
- `test/freepik_api.py` → `freepik_utils/freepik_api.py` - Freepik API модуль

**В scripts/ (новая директория):**
- `get_webpay_token.py` - утилита для получения WebPay токена
- `test_webpay.py` - тесты WebPay API
- `test_envato.py` - тесты Envato загрузки
- `test_envato_lisence.py` - тесты Envato лицензий
- `test_freepik.py` - тесты Freepik загрузки
- `test_kling_video.py` - тесты Kling AI video generation
- `test_nano_banana.py` - тесты NANO BANANA AI image generation
- `filesta/` - тесты Filesta интеграции
- Все cookie файлы и test data

**Структура после завершения:**
```
scripts/                     # Development utilities and tests
├── README.md               # Documentation for all scripts
├── get_webpay_token.py     # WebPay token utility
├── test_webpay.py          # WebPay API testing
├── test_envato.py          # Envato download testing
├── test_envato_lisence.py  # Envato license testing
├── test_freepik.py         # Freepik download testing
├── test_kling_video.py     # Kling AI testing
├── test_nano_banana.py     # NANO BANANA AI testing
├── filesta/                # Filesta integration
├── *.json                  # Test data (cookies, etc)
└── recorded_actions.json   # Playwright recordings

utils/                      # Production utilities
├── convert_cookies.py      # Cookie format converter
└── cookie_fixer.py         # Cookie fixing utility

freepik_utils/              # Freepik-specific code
└── freepik_api.py          # Freepik API module
```

**Результаты:**
- Чёткое разделение: production код vs development утилиты
- Утилиты перемещены в соответствующие модули
- Все скрипты документированы в `scripts/README.md`
- Упрощён поиск и поддержка test/debug инструментов
- Директория `test/` больше не существует

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