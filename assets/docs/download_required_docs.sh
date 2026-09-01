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

mkdir -p   "${script_dir}/ndk"   "${script_dir}/amigaos-wiki"   "${script_dir}/amigaos3-developer"

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

download   "https://aminet.net/dev/misc/NDK3.2.lha"   "${script_dir}/ndk/NDK3.2.lha"

extract_lha   "${script_dir}/ndk/NDK3.2.lha"   "${script_dir}/ndk/NDK3.2"

wiki_pages=(
  "workbench_library.html|https://wiki.amigaos.net/wiki/Workbench_Library"
  "amigaos_manual_workbench.html|https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench"
  "amigaos_manual_workbench_fundamentals.html|https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench_Fundamentals"
  "amigaos_apps_development.html|https://wiki.amigaos.net/wiki/AmigaOS_Apps_Development"
  "programming_in_the_amiga_environment.html|https://wiki.amigaos.net/wiki/Programming_in_the_Amiga_Environment"
  "libraries.html|https://wiki.amigaos.net/wiki/Libraries"
  "exec_libraries.html|https://wiki.amigaos.net/wiki/Exec_Libraries"
  "intuition_library.html|https://wiki.amigaos.net/wiki/Intuition_Library"
  "intuition_gadgets.html|https://wiki.amigaos.net/wiki/Intuition_Gadgets"
  "window_communication.html|https://wiki.amigaos.net/wiki/Window_Communication"
  "icon_library.html|https://wiki.amigaos.net/wiki/Icon_Library"
  "iffparse_library.html|https://wiki.amigaos.net/wiki/IFFParse_Library"
  "parsing_iff.html|https://wiki.amigaos.net/wiki/Parsing_IFF"
  "tags.html|https://wiki.amigaos.net/wiki/Tags"
)

for entry in "${wiki_pages[@]}"; do
  output="${entry%%|*}"
  url="${entry#*|}"
  download "${url}" "${script_dir}/amigaos-wiki/${output}"
done

download   "https://developer.amigaos3.net/article/13-recommended-reading-amiga-developer"   "${script_dir}/amigaos3-developer/recommended_reading.html"

python3 "${script_dir}/fetch_autodocs.py" --keep-going

echo "Done."
echo "Next: run uv run python tools/generate_api_index.py from the repository root."
