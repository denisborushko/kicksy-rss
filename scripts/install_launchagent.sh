#!/bin/bash
# Устанавливает LaunchAgent для автозапуска KICKSY Agent при старте Mac Mini.
# Запускать от имени текущего пользователя (не sudo).

set -e
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USERNAME="$(whoami)"
PLIST_SRC="$AGENT_DIR/scripts/com.kicksy.agent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.kicksy.agent.plist"

echo "👤 Пользователь: $USERNAME"
echo "📁 Директория агента: $AGENT_DIR"

# Подставляем реального пользователя в plist
sed "s|/Users/YOUR_USERNAME|/Users/$USERNAME|g" "$PLIST_SRC" > "$PLIST_DST"

echo "📋 plist скопирован в: $PLIST_DST"

# Загружаем службу
launchctl load "$PLIST_DST"

echo ""
echo "✅ LaunchAgent установлен! KICKSY Agent будет запускаться автоматически."
echo ""
echo "Управление:"
echo "  Остановить:    launchctl unload ~/Library/LaunchAgents/com.kicksy.agent.plist"
echo "  Запустить:     launchctl load   ~/Library/LaunchAgents/com.kicksy.agent.plist"
echo "  Статус:        launchctl list | grep kicksy"
echo "  Логи:          tail -f $AGENT_DIR/logs/launchagent-stdout.log"
