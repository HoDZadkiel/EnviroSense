#!/usr/bin/env bash
# EnviroSense HA 0.2.2-ha  Linux / macOS 燒錄腳本 (XIAO ESP32C6)
# 用法: ./flash.sh /dev/ttyACM0 [full|update]      (macOS: /dev/cu.usbmodemXXXX)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="$HERE/bins/envirosense-ha-0.2.2-esp32c6"

if command -v esptool >/dev/null 2>&1; then ESPTOOL=(esptool)
elif command -v esptool.py >/dev/null 2>&1; then ESPTOOL=(esptool.py)
elif python3 -m esptool version >/dev/null 2>&1; then ESPTOOL=(python3 -m esptool)
else echo "找不到 esptool，請先安裝: pip install esptool / esptool not found: pip install esptool"; exit 1; fi

PORT="$1"; MODE="$2"
if [ -z "$PORT" ]; then
  echo "先讓晶片進燒錄模式: 按住 BOOT - 按一下 RESET - 放開 BOOT"
  read -rp "裝置序列埠 / your serial port (e.g. /dev/ttyACM0): " PORT
fi
if [ -z "$MODE" ]; then
  echo "[1] 全新安裝 full (清空 flash，設定會消失)"
  echo "[2] 更新 update (只換程式，保留設定)"
  read -rp "選擇 / choose 1 or 2: " c
  [ "$c" = "2" ] && MODE=update || MODE=full
fi

if [ "$MODE" = "update" ]; then
  "${ESPTOOL[@]}" --chip esp32c6 -p "$PORT" -b 460800 write-flash 0x10000 "$PREFIX-app.bin"
else
  "${ESPTOOL[@]}" --chip esp32c6 -p "$PORT" -b 460800 write-flash 0x0 "$PREFIX-merged.bin"
fi
echo "完成 / DONE. 按一下 RESET 啟動新韌體。"
