#!/usr/bin/env bash
# Build one nemo release. The release directory is created only after the
# source tree validates, so a missing tarball cannot leave an empty release.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${here}/common.sh"

usage() {
  cat <<'EOF'
Usage: build.sh --sha SHA (--mirror DIR | --tarball FILE) [options]

  --hermes-home PATH     Profile home. Defaults to HERMES_HOME.
  --releases PATH        Release root. Defaults to <home>/releases.
  --build NAME           Directory name under releases/. Defaults to the SHA.
  --mirror DIR           Bare git mirror. Fetched with a timeout.
  --tarball FILE         Fallback GitHub tarball, used when fetch hangs or fails.
  --remote NAME          Mirror remote. Default: origin.
  --fetch-timeout SEC    git fetch / git archive timeout. Default: 90.
  --extra NAME           Pip extra. Default: nemo.
  --uv-cache PATH        UV_CACHE_DIR. Default: the existing value, else ~/.cache/uv.
  --previous PATH        Previous release to copy .python and frontend bits from.
  --staging PATH         Keep this directory when --stop-after is source or frontend.
  --stop-after STEP      source, frontend, or publish (default).
  --skip-frontend        Do not npm ci or build the dashboard.

Audit files land in <home>/upgrade-audits/<build>/.
EOF
}

home="${HERMES_HOME:-}"
sha=""
build=""
releases=""
mirror=""
tarball=""
remote="origin"
fetch_timeout="90"
extra="nemo"
uv_cache=""
previous_opt=""
staging_opt=""
stop_after="publish"
skip_frontend=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hermes-home) home="${2:-}"; shift 2 ;;
    --sha) sha="${2:-}"; shift 2 ;;
    --build) build="${2:-}"; shift 2 ;;
    --releases) releases="${2:-}"; shift 2 ;;
    --mirror) mirror="${2:-}"; shift 2 ;;
    --tarball) tarball="${2:-}"; shift 2 ;;
    --remote) remote="${2:-}"; shift 2 ;;
    --fetch-timeout) fetch_timeout="${2:-}"; shift 2 ;;
    --extra) extra="${2:-}"; shift 2 ;;
    --uv-cache) uv_cache="${2:-}"; shift 2 ;;
    --previous) previous_opt="${2:-}"; shift 2 ;;
    --staging) staging_opt="${2:-}"; shift 2 ;;
    --stop-after) stop_after="${2:-}"; shift 2 ;;
    --skip-frontend) skip_frontend=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -n "${home}" ]] || die "pass --hermes-home or set HERMES_HOME"
[[ -n "${sha}" ]] || die "pass --sha"
[[ "${sha}" =~ ^[0-9a-fA-F]{7,40}$ ]] || die "sha must be 7-40 hex characters"
[[ -n "${mirror}" || -n "${tarball}" ]] || die "pass --mirror and/or --tarball"
[[ "${extra}" =~ ^[A-Za-z0-9_-]+$ ]] || die "invalid extra: ${extra}"
case "${stop_after}" in
  source|frontend|publish) ;;
  *) die "stop-after must be source, frontend, or publish" ;;
esac
if [[ -z "${build}" ]]; then
  build="${sha}"
fi
if [[ "${build}" == "." || "${build}" == ".." || "${build}" == */* ]]; then
  die "invalid build name: ${build}"
fi
[[ "${build}" =~ ^[A-Za-z0-9._-]+$ ]] || die "invalid build name: ${build}"

if [[ -z "${releases}" ]]; then
  releases="${home}/releases"
fi
release_path="${releases}/${build}"
audit="${home}/upgrade-audits/${build}"
staging=""
keep_staging=0
created=0
published=0

if [[ -d "${release_path}" ]]; then
  if [[ -n "$(find "${release_path}" -mindepth 1 -print -quit)" ]]; then
    die "refusing to replace non-empty release ${release_path}"
  fi
  rmdir "${release_path}"
fi

if [[ -n "${staging_opt}" && "${staging_opt}" == "${release_path}" ]]; then
  die "staging and release must be different directories"
fi
mkdir -p "${releases}"
if [[ -n "${staging_opt}" ]]; then
  staging="${staging_opt}"
  mkdir -p "${staging}"
else
  # Same filesystem as the publish rename, so mv is atomic. A failed build
  # leaves .staging-* (removed by the trap), never an empty release directory.
  staging="$(mktemp -d "${releases}/.staging-${build}.XXXXXX")"
fi

cleanup() {
  local status=$?
  trap - EXIT
  if [[ "${created}" == "1" && "${published}" != "1" && -n "${release_path}" && -d "${release_path}" ]]; then
    chmod -R u+w "${release_path}" || true
    rm -rf "${release_path}" || true
  fi
  if [[ -n "${staging}" && -d "${staging}" ]]; then
    if [[ "${status}" != "0" || "${keep_staging}" != "1" ]]; then
      chmod -R u+w "${staging}" || true
      rm -rf "${staging}" || true
    fi
  fi
  exit "${status}"
}
trap cleanup EXIT

pin_args=(-m scripts.deploy.nemo.cli pin-cache)
if [[ -n "${uv_cache}" ]]; then
  pin_args+=(--path "${uv_cache}")
fi
UV_CACHE_DIR="$(nemo_python "${pin_args[@]}")"
export UV_CACHE_DIR

acquire_args=(
  -m scripts.deploy.nemo.cli acquire
  --sha "${sha}"
  --dest "${staging}"
  --timeout "${fetch_timeout}"
  --remote "${remote}"
)
if [[ -n "${mirror}" ]]; then
  acquire_args+=(--mirror "${mirror}")
fi
if [[ -n "${tarball}" ]]; then
  acquire_args+=(--tarball "${tarball}")
fi
method="$(nemo_python "${acquire_args[@]}")"
[[ -f "${staging}/pyproject.toml" ]] || die "source tree has no pyproject.toml"
printf '%s\n' "source ${method}"

write_build_manifest() {
  nemo_python -m scripts.deploy.nemo.cli manifest-set \
    --path "${audit}/manifest.json" \
    --set "build=${build}" \
    --set "sha=${sha}" \
    --set "release_name=${build}" \
    --set "build_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --set "stage=${1}"
}

if [[ "${stop_after}" == "source" ]]; then
  mkdir -p "${audit}"
  write_build_manifest "source"
  keep_staging=1
  printf '%s\n' "staging ${staging}"
  exit 0
fi

command -v uv >/dev/null 2>&1 || die "uv is required on PATH"
mkdir -p "${audit}"

previous_path=""
previous_name=""
if [[ -n "${previous_opt}" ]]; then
  previous_path="${previous_opt}"
  previous_name="$(basename "${previous_opt}")"
elif [[ -L "${releases}/current" ]]; then
  target="$(readlink "${releases}/current")"
  previous_name="$(basename "${target}")"
  if [[ "${target}" == /* ]]; then
    previous_path="${target}"
  else
    previous_path="${releases}/${target}"
  fi
fi

copy_tree() {
  local src="$1"
  local dest="$2"
  if [[ ! -e "${src}" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "${dest}")"
  rm -rf "${dest}"
  cp -a "${src}" "${dest}"
}

locks_match() {
  local prev="$1"
  local tree="$2"
  [[ -f "${prev}/package-lock.json" && -f "${tree}/package-lock.json" ]] || return 1
  cmp -s "${prev}/package-lock.json" "${tree}/package-lock.json"
}

if [[ -n "${previous_path}" && -d "${previous_path}" ]]; then
  printf '%s\n' "copying .python and frontend artifacts from ${previous_path}"
  copy_tree "${previous_path}/.python" "${staging}/.python"
  copy_tree "${previous_path}/hermes_cli/web_dist" "${staging}/hermes_cli/web_dist"
  copy_tree "${previous_path}/ui-tui/dist" "${staging}/ui-tui/dist"
  if locks_match "${previous_path}" "${staging}"; then
    copy_tree "${previous_path}/node_modules" "${staging}/node_modules"
  fi
fi

venv_python="${staging}/.venv/bin/python"
if [[ -x "${staging}/.python/bin/python3" ]]; then
  uv venv "${staging}/.venv" --python "${staging}/.python/bin/python3"
elif [[ -x "${staging}/.python/bin/python" ]]; then
  uv venv "${staging}/.venv" --python "${staging}/.python/bin/python"
else
  uv venv "${staging}/.venv"
fi

install_args=(pip install --python "${venv_python}")
if [[ -n "${previous_path}" && -f "${previous_path}/freeze.txt" ]]; then
  cp "${previous_path}/freeze.txt" "${audit}/old-freeze.txt"
  nemo_python -m scripts.deploy.nemo.cli freeze-constraint \
    --input "${audit}/old-freeze.txt" --output "${audit}/constraints.txt"
  install_args+=(-c "${audit}/constraints.txt")
fi
install_args+=(-e ".[${extra}]")
(
  cd "${staging}"
  uv "${install_args[@]}"
)
uv pip freeze --python "${venv_python}" > "${audit}/freeze.txt"
cp "${audit}/freeze.txt" "${staging}/freeze.txt"
if [[ -f "${audit}/old-freeze.txt" ]]; then
  nemo_python -m scripts.deploy.nemo.cli freeze-compare \
    --old "${audit}/old-freeze.txt" --new "${audit}/freeze.txt" \
    --report "${audit}/freeze-diff.txt"
fi
"${venv_python}" -c "import hermes_cli, requests, yaml"

if [[ "${skip_frontend}" != "1" ]]; then
  command -v node >/dev/null 2>&1 || die "node is required to preinstall dashboard dependencies"
  node "${staging}/scripts/build/node-deps.mjs" \
    --source "${staging}" --reuse --workspace ui-tui --workspace web
  tui_fresh="$(node "${staging}/scripts/build/freshness.mjs" \
    --source "${staging}" --product tui --out "${staging}/ui-tui/dist")"
  if [[ "${tui_fresh}" != "true" ]]; then
    node "${staging}/scripts/build/tui.mjs"
  fi
  web_fresh="$(node "${staging}/scripts/build/freshness.mjs" \
    --source "${staging}" --product web --out "${staging}/hermes_cli/web_dist")"
  if [[ "${web_fresh}" != "true" ]]; then
    node "${staging}/scripts/build/web.mjs"
  fi
  nemo_python -m scripts.deploy.nemo.cli mark-frontend --release "${staging}"
fi

if [[ "${stop_after}" == "frontend" ]]; then
  write_build_manifest "frontend"
  keep_staging=1
  printf '%s\n' "staging ${staging}"
  exit 0
fi

mkdir -p "${releases}"
mv "${staging}" "${release_path}"
staging=""
created=1
# Tool sources are read by an interpreter, never executed. Publishing them without the exec bit
# makes any launch that still depends on it fail the cutover selftest instead of a user's call.
find "${release_path}/tools" -type f -name '*.py' -exec chmod a-x {} +
chmod -R a-w "${release_path}"
published=1

manifest_args=(
  -m scripts.deploy.nemo.cli manifest-set
  --path "${audit}/manifest.json"
  --set "build=${build}"
  --set "sha=${sha}"
  --set "release_name=${build}"
  --set "build_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  --set "release=${release_path}"
  --set "releases=${releases}"
  --set "source=${method}"
  --set "uv_cache_dir=${UV_CACHE_DIR}"
  --set "extra=${extra}"
  --set "stage=publish"
)
if [[ -n "${previous_name}" ]]; then
  manifest_args+=(--set "previous=${previous_name}")
fi
nemo_python "${manifest_args[@]}"
printf '%s\n' "published ${release_path}"
