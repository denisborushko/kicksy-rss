#!/bin/bash
# KICKSY Agent — Setup Script
# Запустить один раз после переноса на Mac Mini:
#   chmod +x scripts/setup.sh && ./scripts/setup.sh

set -e
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$AGENT_DIR"

echo "📁 Рабочая директория: $AGENT_DIR"

# 1. Python venv
echo ""
echo "🐍 Создаём виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

# 2. Зависимости
echo ""
echo "📦 Устанавливаем зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚙️  Копируем .env.example → .env"
    cp .env.example .env
    echo "   ⚠️  Отредактируй .env и вставь реальные токены!"
fi

# 4. Папки state/ и logs/
mkdir -p state logs

echo ""
echo "✅ Установка завершена!"
echo ""
echo "Следующие шаги:"
echo "  1. Отредактируй .env — вставь токены VK и настройки"
echo "  2. Авторизуй YouTube один раз: python main.py  (откроется браузер)"
echo "  3. Настрой автозапуск: ./scripts/install_launchagent.sh"
