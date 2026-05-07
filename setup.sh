#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SCRIPT="${SCRIPT_DIR}/miraeping.sh"
TARGET_DIR="${HOME}/.miraeping"
TARGET_SCRIPT="${TARGET_DIR}/miraeping"
CREDENTIAL_FILE="${TARGET_DIR}/credentials"
BASHRC="${HOME}/.bashrc"
SOURCE_LINE="source ~/.miraeping/miraeping"
OLD_SOURCE_LINE="source ~/.miraeping.sh"

if [[ ! -f "${SOURCE_SCRIPT}" ]]; then
  echo "Error: cannot find ${SOURCE_SCRIPT}"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is required for bash mode but was not found in PATH."
  exit 1
fi

touch "${BASHRC}"
mkdir -p "${TARGET_DIR}"
chmod 700 "${TARGET_DIR}"

is_interactive() {
  [[ -t 0 ]]
}

validate_slack_user_id() {
  [[ "${1:-}" =~ ^[UW][A-Z0-9]{8,}$ ]]
}

validate_slack_bot_token() {
  [[ "${1:-}" =~ ^xoxb-[A-Za-z0-9-]+$ ]]
}

prompt_masked() {
  local prompt="$1"
  local validator="$2"
  local invalid_message="$3"
  local value=""

  while true; do
    read -r -s -p "${prompt}" value
    echo >&2

    if [[ -z "${value}" ]]; then
      echo "Input cannot be empty. Please try again." >&2
      continue
    fi

    if ! "${validator}" "${value}"; then
      echo "${invalid_message}" >&2
      continue
    fi

    printf '%s' "${value}"
    return
  done
}

resolve_credential() {
  local key="$1"
  local prompt="$2"
  local validator="$3"
  local invalid_message="$4"
  local env_value="${!key-}"

  if [[ -n "${env_value}" ]]; then
    if ! "${validator}" "${env_value}"; then
      echo "Error: ${key} is set but has invalid format." >&2
      echo "${invalid_message}" >&2
      exit 1
    fi
    printf '%s' "${env_value}"
    return
  fi

  if ! is_interactive; then
    echo "Error: ${key} is not set and no interactive terminal is available." >&2
    echo "Set ${key} environment variable and re-run setup.sh." >&2
    exit 1
  fi

  prompt_masked "${prompt}" "${validator}" "${invalid_message}"
}

has_source_line() {
  grep -Fqx "${SOURCE_LINE}" "${BASHRC}"
}

has_old_source_line() {
  grep -Fqx "${OLD_SOURCE_LINE}" "${BASHRC}"
}

replace_old_source_line() {
  local tmp_file
  tmp_file="$(mktemp -p "${TARGET_DIR}")"

  while IFS= read -r line || [[ -n "${line}" ]]; do
    if [[ "${line}" == "${OLD_SOURCE_LINE}" ]]; then
      printf '%s\n' "${SOURCE_LINE}" >> "${tmp_file}"
    else
      printf '%s\n' "${line}" >> "${tmp_file}"
    fi
  done < "${BASHRC}"

  mv "${tmp_file}" "${BASHRC}"
}

write_credentials_file() {
  local user_id="$1"
  local bot_token="$2"
  local tmp_file

  tmp_file="${CREDENTIAL_FILE}.tmp"
  umask 077
  {
    printf 'SLACK_USER_ID=%s\n' "${user_id}"
    printf 'SLACK_BOT_TOKEN=%s\n' "${bot_token}"
  } > "${tmp_file}"

  mv "${tmp_file}" "${CREDENTIAL_FILE}"
  chmod 600 "${CREDENTIAL_FILE}"
}

echo "Installing miraeping helper..."
cp "${SOURCE_SCRIPT}" "${TARGET_SCRIPT}"
chmod 700 "${TARGET_SCRIPT}"

echo
echo "Enter Slack credentials (or pre-set SLACK_USER_ID / SLACK_BOT_TOKEN env vars)."
SLACK_USER_ID="$(resolve_credential "SLACK_USER_ID" "1) Slack User ID (hidden input): " validate_slack_user_id "Slack User ID must look like U012AB3CD.")"
SLACK_BOT_TOKEN="$(resolve_credential "SLACK_BOT_TOKEN" "2) Slack Bot Token (hidden input): " validate_slack_bot_token "Slack Bot Token must start with xoxb-.")"

write_credentials_file "${SLACK_USER_ID}" "${SLACK_BOT_TOKEN}"

if has_old_source_line; then
  replace_old_source_line
  echo "migrated source line: ${OLD_SOURCE_LINE} -> ${SOURCE_LINE}"
fi

if has_source_line; then
  echo "source line already exists in ~/.bashrc"
else
  {
    echo
    echo "# miraeping / slack notify"
    echo "${SOURCE_LINE}"
  } >> "${BASHRC}"
  echo "added source block to ~/.bashrc"
fi

echo
echo "Setup complete."
echo "Installed script: ${TARGET_SCRIPT}"
echo "Credentials file: ${CREDENTIAL_FILE}"
echo "Run: source ~/.bashrc"
