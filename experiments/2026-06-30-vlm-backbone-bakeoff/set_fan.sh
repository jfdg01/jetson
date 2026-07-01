#!/usr/bin/env bash
# NON-FUNCTIONAL ON THIS CARD — kept as the record of what was tried (README
# 2026-07-01T11:20Z fan finding): Coolbits=4 is active and GPUFanControlState
# assigns, but every GPUTargetFanSpeed write throws "Unknown Error" (driver/VBIOS
# rejects it, driver 595). The working noise lever is the power cap instead:
#   sudo nvidia-smi -pl 220   # ~75% fan, ~14% throughput cost (not reboot-persistent)
#
# Original intent: both RTX 3090 fans to a fixed 80% via nvidia-settings on :0.
# Usage: bash set_fan.sh [percent]
PCT="${1:-80}"
export DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority
nvidia-settings \
  -a '[gpu:0]/GPUFanControlState=1' \
  -a "[fan:0]/GPUTargetFanSpeed=$PCT" \
  -a "[fan:1]/GPUTargetFanSpeed=$PCT" 2>&1 | grep -iE 'assigned|error'
sleep 4
nvidia-smi --query-gpu=fan.speed,temperature.gpu,power.draw --format=csv,noheader
