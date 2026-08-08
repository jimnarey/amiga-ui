#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 <command> [args...]" >&2
}

if [[ "$#" -eq 0 ]]; then
  usage
  exit 64
fi

if ! command -v Xvfb >/dev/null 2>&1; then
  echo "Xvfb is not available. Run ./check_optional_deps.sh for guidance." >&2
  exit 127
fi

if [[ -d /tmp/.X11-unix ]]; then
  socket_owner_uid="$(stat -c '%u' /tmp/.X11-unix)"
  socket_mode="$(stat -c '%a' /tmp/.X11-unix)"
  if [[ "${socket_owner_uid}" != "0" ]]; then
    echo "/tmp/.X11-unix is owned by uid ${socket_owner_uid}, but Xvfb expects root ownership." >&2
    echo "Suggested host fix: sudo chown root:root /tmp/.X11-unix" >&2
    exit 1
  fi
  if [[ "${socket_mode}" != "1777" ]]; then
    echo "/tmp/.X11-unix has mode ${socket_mode}, but Xvfb expects 1777." >&2
    echo "Suggested host fix: sudo chmod 1777 /tmp/.X11-unix" >&2
    exit 1
  fi
fi

screen_spec="${AMIGA_UI_XVFB_SCREEN:-1280x1024x24}"
requested_display="${AMIGA_UI_XVFB_DISPLAY:-}"
runtime_dir="$(mktemp -d /tmp/amiga-ui-xvfb.XXXXXX)"
xvfb_log="${runtime_dir}/xvfb.log"
xvfb_pid=""
display=""
start_failure_message=""

cleanup() {
  if [[ -n "${xvfb_pid}" ]] && kill -0 "${xvfb_pid}" >/dev/null 2>&1; then
    kill "${xvfb_pid}" >/dev/null 2>&1 || true
    wait "${xvfb_pid}" >/dev/null 2>&1 || true
  fi
  rm -rf "${runtime_dir}"
}

start_xvfb() {
  local candidate="$1"

  Xvfb "${candidate}" -screen 0 "${screen_spec}" -nolisten tcp >"${xvfb_log}" 2>&1 &
  xvfb_pid="$!"

  for _ in $(seq 1 20); do
    if ! kill -0 "${xvfb_pid}" >/dev/null 2>&1; then
      wait "${xvfb_pid}" >/dev/null 2>&1 || true
      start_failure_message="$(tr '\n' ' ' <"${xvfb_log}")"
      xvfb_pid=""
      return 1
    fi
    sleep 0.1
  done

  display="${candidate}"
  return 0
}

trap cleanup EXIT

if [[ -n "${requested_display}" ]]; then
  if ! start_xvfb "${requested_display}"; then
    echo "Unable to start Xvfb on display ${requested_display}." >&2
    if [[ -n "${start_failure_message}" ]]; then
      echo "Xvfb output: ${start_failure_message}" >&2
    fi
    exit 1
  fi
else
  for candidate_number in $(seq 90 110); do
    if start_xvfb ":${candidate_number}"; then
      break
    fi
  done
fi

if [[ -z "${display}" ]]; then
  echo "Unable to find a usable Xvfb display." >&2
  if [[ -n "${start_failure_message}" ]]; then
    echo "Last Xvfb output: ${start_failure_message}" >&2
  fi
  exit 1
fi

export DISPLAY="${display}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

"$@"
