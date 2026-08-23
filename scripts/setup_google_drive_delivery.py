#!/usr/bin/env python3
"""
scripts/setup_google_drive_delivery.py

Одноразовая настройка доставки финального видео из GitHub Actions в Google Drive.

Что делает:
  1. Проверяет brew, rclone, gh — ставит недостающее.
  2. Проверяет авторизацию gh, при необходимости запускает `gh auth login --web`
     (браузерная авторизация, без ручного копирования токенов).
  3. Запускает интерактивную настройку rclone для Google Drive (remote с именем "gdrive").
  4. Проверяет доступность Google Drive через `rclone lsd gdrive:`.
  5. Находит реальный путь к rclone.conf через `rclone config file` (не угадывает путь).
  6. Кодирует конфиг в base64 и кладёт в GitHub Secret RCLONE_CONFIG_BASE64
     для репозитория mdbiplob66789-wq/romanian-documentary-factory.
  7. Проверяет, что secret действительно создан/обновлён.

Ничего не выводит: сам rclone.conf, секрет в base64, OAuth-токены.
Ничего не пишет в репозиторий и не коммитит rclone.conf.

Запуск: python3 scripts/setup_google_drive_delivery.py
"""

import base64
import shutil
import subprocess
import sys

REPO = "mdbiplob66789-wq/romanian-documentary-factory"
REMOTE_NAME = "gdrive"
SECRET_NAME = "RCLONE_CONFIG_BASE64"


def step(title):
    print()
    print(f"== {title} ==")


def fail(message):
    print(f"\nОШИБКА: {message}", file=sys.stderr)
    sys.exit(1)


def run(cmd, **kwargs):
    """Запуск команды без захвата вывода — для интерактивных шагов (rclone config, gh auth login)."""
    return subprocess.run(cmd, **kwargs)


def run_captured(cmd, check=True):
    """Запуск команды с захватом stdout/stderr — для тихих проверочных вызовов."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def check_brew():
    step("Проверка Homebrew")
    if shutil.which("brew") is None:
        fail(
            "Homebrew не найден. Установите его вручную: https://brew.sh\n"
            "Без него скрипт не может автоматически поставить rclone/gh."
        )
    print("brew найден:", shutil.which("brew"))


def ensure_tool(name, brew_formula=None):
    """Проверяет наличие CLI-инструмента, при отсутствии ставит через brew."""
    formula = brew_formula or name
    if shutil.which(name):
        print(f"{name} уже установлен: {shutil.which(name)}")
        return
    step(f"Установка {name} через Homebrew")
    result = run(["brew", "install", formula])
    if result.returncode != 0 or shutil.which(name) is None:
        fail(f"Не удалось установить {name} через 'brew install {formula}'. Установите вручную и запустите скрипт заново.")
    print(f"{name} установлен.")


def ensure_gh_auth():
    step("Проверка авторизации GitHub CLI (gh)")
    result = run_captured(["gh", "auth", "status"], check=False)
    if result.returncode == 0:
        print("gh уже авторизован.")
        return

    print("gh не авторизован. Сейчас откроется браузер для входа в GitHub.")
    print("Токен копировать вручную не нужно — просто подтвердите вход в браузере.")
    login = run(["gh", "auth", "login", "--web", "--git-protocol", "https"])
    if login.returncode != 0:
        fail("Авторизация gh не завершилась успешно. Запустите 'gh auth login --web' вручную и повторите скрипт.")

    verify = run_captured(["gh", "auth", "status"], check=False)
    if verify.returncode != 0:
        fail("После входа gh всё ещё не авторизован. Попробуйте 'gh auth login' вручную.")
    print("gh авторизован.")


def ensure_gh_repo_access():
    step(f"Проверка доступа к репозиторию {REPO}")
    result = run_captured(["gh", "repo", "view", REPO], check=False)
    if result.returncode != 0:
        fail(
            f"Нет доступа к репозиторию {REPO} через gh.\n"
            "Проверьте, что вы вошли под аккаунтом, у которого есть права на этот репозиторий."
        )
    print("Доступ к репозиторию подтверждён.")


def remote_exists():
    result = run_captured(["rclone", "listremotes"], check=False)
    if result.returncode != 0:
        return False
    remotes = [r.strip().rstrip(":") for r in result.stdout.splitlines()]
    return REMOTE_NAME in remotes


def setup_rclone_remote():
    step("Настройка Google Drive в rclone")
    if remote_exists():
        print(f"Remote '{REMOTE_NAME}:' уже существует, повторная настройка не требуется.")
        return

    print(f"Сейчас запустится интерактивный мастер rclone.")
    print(f"Важно: создайте remote с именем ровно '{REMOTE_NAME}' (без кавычек).")
    print("Тип хранилища — Google Drive (в списке ищите 'Google Drive').")
    print("Scope — 1 (полный доступ, full access).")
    print("На вопрос про автоматическую конфигурацию (auto config) отвечайте 'y' —")
    print("откроется браузер для входа в Google-аккаунт.")
    input("\nНажмите Enter, чтобы продолжить...")

    result = run(["rclone", "config"])
    if result.returncode != 0:
        fail("Мастер rclone config завершился с ошибкой. Запустите 'rclone config' вручную и создайте remote 'gdrive'.")

    if not remote_exists():
        fail(
            f"Remote '{REMOTE_NAME}:' не найден после настройки.\n"
            f"Запустите скрипт ещё раз и убедитесь, что имя remote указано ровно как '{REMOTE_NAME}'."
        )
    print(f"Remote '{REMOTE_NAME}:' создан.")


def verify_drive_access():
    step("Проверка доступности Google Drive")
    result = run_captured(["rclone", "lsd", f"{REMOTE_NAME}:"], check=False)
    if result.returncode != 0:
        fail(
            "Не удалось подключиться к Google Drive через rclone.\n"
            f"Команда 'rclone lsd {REMOTE_NAME}:' вернула ошибку:\n{result.stderr.strip()}\n"
            "Возможно, авторизация не завершена или remote настроен неверно. "
            "Попробуйте 'rclone config reconnect gdrive:' или пересоздайте remote."
        )
    print("Google Drive доступен, соединение подтверждено.")


def find_rclone_config_path():
    step("Поиск фактического пути к rclone.conf")
    result = run_captured(["rclone", "config", "file"], check=False)
    if result.returncode != 0:
        fail("Команда 'rclone config file' завершилась с ошибкой — не удалось определить путь к конфигу.")

    # Вывод обычно двухстрочный:
    # "Configuration file is stored at:\n/actual/path/rclone.conf"
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    if not lines:
        fail("Не удалось прочитать путь к rclone.conf из вывода 'rclone config file'.")
    config_path = lines[-1]
    print(f"Реальный путь к конфигу: {config_path}")
    return config_path


def read_and_encode_config(config_path):
    step("Чтение и кодирование rclone.conf")
    try:
        with open(config_path, "rb") as f:
            raw = f.read()
    except OSError as e:
        fail(f"Не удалось прочитать {config_path}: {e}")

    if not raw.strip():
        fail(f"Файл {config_path} пустой — настройка rclone, похоже, не завершена.")

    encoded = base64.b64encode(raw).decode("ascii")
    print(f"Конфиг прочитан и закодирован ({len(raw)} байт исходно). Содержимое нигде не выводится.")
    return encoded


def set_github_secret(encoded_value):
    step(f"Запись GitHub Secret {SECRET_NAME}")
    # Передаём значение через stdin, а не как аргумент командной строки —
    # чтобы секрет не попал в список процессов (ps) и в историю шелла.
    result = subprocess.run(
        ["gh", "secret", "set", SECRET_NAME, "--repo", REPO],
        input=encoded_value,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        fail(f"Не удалось записать secret {SECRET_NAME}:\n{result.stderr.strip()}")
    print(f"Secret {SECRET_NAME} записан в репозиторий {REPO}.")


def verify_secret_exists():
    step("Проверка, что secret действительно создан")
    result = run_captured(["gh", "secret", "list", "--repo", REPO], check=False)
    if result.returncode != 0:
        fail("Не удалось получить список secrets репозитория для проверки.")
    names = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    if SECRET_NAME not in names:
        fail(f"Secret {SECRET_NAME} не найден в списке secrets репозитория после записи.")
    print(f"Подтверждено: {SECRET_NAME} есть в secrets репозитория {REPO}.")


def main():
    print("Настройка доставки финального видео в Google Drive через GitHub Actions.")
    print(f"Репозиторий: {REPO}")
    print(f"Remote rclone: {REMOTE_NAME}")
    print(f"GitHub Secret: {SECRET_NAME}")

    check_brew()
    ensure_tool("rclone")
    ensure_tool("gh")
    ensure_gh_auth()
    ensure_gh_repo_access()
    setup_rclone_remote()
    verify_drive_access()
    config_path = find_rclone_config_path()
    encoded = read_and_encode_config(config_path)
    set_github_secret(encoded)
    verify_secret_exists()

    print()
    print("ГОТОВО.")
    print("GitHub Actions теперь может загружать финальное видео прямо в Google Drive")
    print("под именем URME_RECI_FINAL_YOUTUBE.mp4 (перезаписывая предыдущую версию).")
    print("Дальше ничего вручную собирать/скачивать не нужно — запустите workflow 'Render documentary'.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано пользователем.", file=sys.stderr)
        sys.exit(130)
