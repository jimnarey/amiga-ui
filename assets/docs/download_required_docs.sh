#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 1
fi

if ! command -v 7z >/dev/null 2>&1; then
  echo "error: 7z is required" >&2
  exit 1
fi

mkdir -p \
  "${script_dir}/ndk" \
  "${script_dir}/amigaos-wiki" \
  "${script_dir}/amigaos3-developer"

download() {
  local url="$1"
  local output="$2"

  echo "Downloading ${url}"
  curl -L --fail --max-time 300 --output "${output}" "${url}"
}

extract_lha() {
  local archive_path="$1"
  local extract_dir="$2"

  rm -rf "${extract_dir}"
  mkdir -p "${extract_dir}"
  7z x -y "-o${extract_dir}" "${archive_path}" >/dev/null
}

download \
  "https://aminet.net/dev/misc/NDK3.2.lha" \
  "${script_dir}/ndk/NDK3.2.lha"

extract_lha \
  "${script_dir}/ndk/NDK3.2.lha" \
  "${script_dir}/ndk/NDK3.2"

download \
  "https://wiki.amigaos.net/wiki/Workbench_Library" \
  "${script_dir}/amigaos-wiki/workbench_library.html"

download \
  "https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench" \
  "${script_dir}/amigaos-wiki/amigaos_manual_workbench.html"

download \
  "https://wiki.amigaos.net/wiki/AmigaOS_Apps_Development" \
  "${script_dir}/amigaos-wiki/amigaos_apps_development.html"

download \
  "https://developer.amigaos3.net/autodocs/dos.library/" \
  "${script_dir}/amigaos3-developer/dos.library.html"

download \
  "https://developer.amigaos3.net/article/13-recommended-reading-amiga-developer" \
  "${script_dir}/amigaos3-developer/recommended_reading.html"

echo "Done."
