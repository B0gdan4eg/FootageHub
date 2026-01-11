"""
Скрипт для автоматической миграции старых CRUD импортов на репозитории.
"""
import re
from pathlib import Path

# Маппинг старых функций на новые методы репозиториев
CRUD_MAPPINGS = {
    # user_crud
    "get_user_by_telegram_id": ("UserRepository", "get_by_telegram_id"),
    "create_user": ("UserRepository", "create_user"),
    "get_or_create_user": ("UserRepository", "get_or_create_by_telegram_id"),
    "add_user_credits": ("UserRepository", "add_credits"),
    "get_all_users": ("UserRepository", "get_all_users"),
    "grant_access": ("UserRepository", "grant_access"),
    "set_user_referrer": ("UserRepository", "set_user_referrer"),
    # subscription_crud
    "get_active_subscription": ("SubscriptionRepository", "get_active_by_user_id"),
    "create_subscription": ("SubscriptionRepository", "create_subscription_with_credits"),
    "check_download_limit": ("SubscriptionRepository", "check_download_limit"),
    "increment_download_count": ("SubscriptionRepository", "increment_usage"),
    "get_user_subscriptions": ("SubscriptionRepository", "get_user_subscriptions"),
    "count_active_subs": ("SubscriptionRepository", "count_active_subs"),
    # payment_crud
    "create_payment": ("PaymentRepository", "create_payment"),
    "get_payment_by_invoice_id": ("PaymentRepository", "get_by_invoice_id"),
    "update_payment_status": ("PaymentRepository", "update_status"),
    "mark_payment_success": ("PaymentRepository", "mark_success"),
    # downloaded_file_crud
    "get_media_by_url": ("MediaRepository", "get_by_url"),
    "create_media": ("MediaRepository", "get_or_create"),
    "create_download": ("DownloadRepository", "create_download"),
    "count_downloads_by_user": ("DownloadRepository", "count_by_user"),
    "count_total_downloads": ("DownloadRepository", "count_total"),
    # referral_crud
    "create_referral_code": ("ReferralRewardRepository", "create_referral_code"),
    "apply_referral_code": ("ReferralRewardRepository", "apply_referral_code"),
    "create_referral_reward": ("ReferralRewardRepository", "create_reward"),
    "complete_referral_reward": ("ReferralRewardRepository", "complete_reward"),
    "get_referral_stats": ("ReferralRewardRepository", "get_stats"),
    "get_user_referrals": ("ReferralRewardRepository", "get_user_referrals"),
    "get_pending_rewards": ("ReferralRewardRepository", "get_pending_rewards"),
}

# Список файлов для миграции
FILES_TO_MIGRATE = [
    "media_bot/handlers/referral.py",
    "media_bot/handlers/download/envato.py",
    "media_bot/handlers/download/freepik.py",
    "media_bot/handlers/download/motion.py",
    "media_bot/handlers/download/validators.py",
    "media_bot/handlers/admin/subscriptions.py",
    "media_bot/webhook/webpay.py",
    "media_bot/webhook/cryptobot.py",
    "media_bot/schedule_tasks.py",
]


def migrate_file(file_path: Path):
    """Мигрировать один файл."""
    print(f"\n📄 Обработка: {file_path}")

    if not file_path.exists():
        print(f"  ⚠️  Файл не найден: {file_path}")
        return

    content = file_path.read_text(encoding="utf-8")
    original_content = content

    # Найти все импорты из shared.db.*_crud
    import_pattern = r"from shared\.db\.(user_crud|subscription_crud|payment_crud|downloaded_file_crud|referral_crud) import ([^\n]+)"
    imports_found = re.findall(import_pattern, content)

    if not imports_found:
        print(f"  ✅ Нет старых импортов")
        return

    # Собираем необходимые репозитории
    repos_needed = set()
    for crud_module, functions_str in imports_found:
        # Парсим импортированные функции
        functions = [f.strip() for f in functions_str.split(",")]
        for func in functions:
            if func in CRUD_MAPPINGS:
                repo_name, _ = CRUD_MAPPINGS[func]
                repos_needed.add(repo_name)

    # Заменяем импорты
    new_import = f"from shared.db.repositories import {', '.join(sorted(repos_needed))}"

    # Удаляем все старые импорты
    content = re.sub(import_pattern, "", content)

    # Добавляем новый импорт после других импортов из shared.db
    session_import_pattern = r"(from shared\.db\.session import [^\n]+)"
    if re.search(session_import_pattern, content):
        content = re.sub(session_import_pattern, f"\\1\n{new_import}", content)
    else:
        # Если нет импорта session, добавляем после импортов models
        models_import_pattern = r"(from shared\.db\.models import [^\n]+)"
        if re.search(models_import_pattern, content):
            content = re.sub(models_import_pattern, f"\\1\n{new_import}", content)

    # Очищаем пустые строки
    content = re.sub(r"\n\n\n+", "\n\n", content)

    if content != original_content:
        file_path.write_text(content, encoding="utf-8")
        print(f"  ✅ Импорты обновлены")
        print(f"     Репозитории: {', '.join(sorted(repos_needed))}")
    else:
        print(f"  ℹ️  Файл не изменён")


def main():
    """Главная функция."""
    print("🚀 Начало миграции CRUD -> Repositories\n")
    print("=" * 60)

    root = Path(__file__).parent.parent

    for file_rel_path in FILES_TO_MIGRATE:
        file_path = root / file_rel_path
        migrate_file(file_path)

    print("\n" + "=" * 60)
    print("✅ Миграция импортов завершена!")
    print("\n⚠️  ВНИМАНИЕ: Необходимо вручную заменить вызовы функций")
    print("    на методы репозиториев в каждом файле!")


if __name__ == "__main__":
    main()
