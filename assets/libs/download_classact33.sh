#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
archive_path="${script_dir}/classact33.lha"
extract_dir="${script_dir}/classact33"
download_url="https://aminet.net/dev/gui/classact33.lha"

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required" >&2
  exit 1
fi

extract_archive() {
  if command -v 7z >/dev/null 2>&1; then
    7z x -y "-o${extract_dir}" "${archive_path}" >/dev/null
    return
  fi

  echo "error: no supported extractor found; install 7z" >&2
  exit 1
}

mkdir -p "${script_dir}"

echo "Downloading classact33 archive..."
curl -L --fail --max-time 300 --output "${archive_path}" "${download_url}"

rm -rf "${extract_dir}"
mkdir -p "${extract_dir}"

echo "Extracting archive to ${extract_dir}..."
extract_archive

find "${extract_dir}" -type f | sort >"${extract_dir}/FILES.txt"

if find "${extract_dir}" -type f \( -iname '*.fd' -o -iname '*.h' -o -iname '*.i' -o -iname '*.doc' -o -iname '*.guide' -o -iname '*.readme' \) | grep -q .; then
  find "${extract_dir}" -type f     \( -iname '*.fd' -o -iname '*.h' -o -iname '*.i' -o -iname '*.doc' -o -iname '*.guide' -o -iname '*.readme' \)     | sort >"${extract_dir}/REFERENCE_FILES.txt"
fi

echo "Done."
echo "Archive kept at: ${archive_path}"
echo "Extracted files at: ${extract_dir}"
echo "File manifest: ${extract_dir}/FILES.txt"
