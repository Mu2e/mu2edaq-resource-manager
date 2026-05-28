# Shared helper, meant to be sourced (not executed) by the other scripts.
#
# Loads KEY=VALUE pairs from the project's .env file into the environment.
# A variable already set in the real environment is NOT overridden, preserving
# the priority: commandline > environment > .env > config > defaults.
#
# Override the file location with RM_ENV_FILE. Lines that are blank or begin
# with '#' are ignored; an optional leading "export " is stripped; surrounding
# single or double quotes are removed from the value.

__le_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__le_project="$(dirname "$__le_dir")"
RM_ENV_FILE="${RM_ENV_FILE:-$__le_project/.env}"

if [ -f "$RM_ENV_FILE" ]; then
    while IFS='=' read -r __le_key __le_val || [ -n "$__le_key" ]; do
        case "$__le_key" in
            ''|\#*) continue ;;
        esac
        __le_key="${__le_key#export }"
        __le_key="${__le_key// /}"
        [ -n "$__le_key" ] || continue
        case "$__le_val" in
            \"*\") __le_val="${__le_val#\"}"; __le_val="${__le_val%\"}" ;;
            \'*\') __le_val="${__le_val#\'}"; __le_val="${__le_val%\'}" ;;
        esac
        if [ -z "${!__le_key:-}" ]; then
            export "$__le_key=$__le_val"
        fi
    done < "$RM_ENV_FILE"
    unset __le_key __le_val
fi
unset __le_dir __le_project
