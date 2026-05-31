#!/bin/bash
# Mac Keep-Awake Setup
# Run once: sh ~/AgenticHub/Persgraph/scripts/mac-keep-awake.sh
# -----------------------------------------------------------------
# Never sleep on AC power (charger)
sudo pmset -c sleep 0

# Display off after 10 min on AC (saves screen, doesn't block processes)
sudo pmset -c displaysleep 10

# Power Nap: background tasks run even when display is off
sudo pmset -a powernap 1

# Keep TCP connections alive during display sleep (Telegram stays connected)
sudo pmset -a tcpkeepalive 1

echo ""
echo "✅ Done! Current settings:"
pmset -g | grep -E "^\s*(sleep |displaysleep|powernap|tcpkeepalive)"
echo ""
echo "Mac will now stay awake when plugged in."
echo "Display turns off after 10 min but OpenClaw keeps running."
