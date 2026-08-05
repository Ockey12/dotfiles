#!/bin/zsh

emulate -L zsh
setopt EXTENDED_GLOB NO_UNSET PIPE_FAIL

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin${PATH:+:${PATH}}"
export GIT_TERMINAL_PROMPT=0

typeset -gr SCRIPT_DIR="${0:A:h}"
typeset -gr DEFAULT_REPOSITORY_LIST="${SCRIPT_DIR}/libraries.txt"
typeset -gr SKIP_RESULT=20

typeset -g VALIDATION_ERROR=""

log() {
    local level="$1"
    shift

    printf '[%s] [%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$level" "$*"
}

resolve_repository_dir() {
    local repository_url="$1"
    local output

    if ! output="$("$ghq_bin" list --full-path --exact -- "$repository_url")"; then
        return 1
    fi

    [[ -n "$output" ]] || return 3
    [[ "$output" != *$'\n'* ]] || return 4

    print -r -- "$output"
}

validate_repository() {
    local repository_dir="$1"
    local repository_url="$2"
    local inside_worktree
    local worktree_status
    local current_branch
    local upstream_branch
    local origin_url
    local origin_repository_dir
    local lookup_result
    local ahead_count

    VALIDATION_ERROR=""

    if ! inside_worktree="$("$git_bin" -C "$repository_dir" rev-parse --is-inside-work-tree 2>/dev/null)" ||
        [[ "$inside_worktree" != "true" ]]; then
        VALIDATION_ERROR="not a Git worktree: $repository_dir"
        return 1
    fi

    if ! worktree_status="$("$git_bin" -C "$repository_dir" status --porcelain --untracked-files=normal)"; then
        VALIDATION_ERROR="failed to inspect worktree: $repository_dir"
        return 1
    fi
    if [[ -n "$worktree_status" ]]; then
        VALIDATION_ERROR="worktree is dirty: $repository_dir"
        return 1
    fi

    if ! current_branch="$("$git_bin" -C "$repository_dir" symbolic-ref --quiet --short HEAD)"; then
        VALIDATION_ERROR="HEAD is detached: $repository_dir"
        return 1
    fi
    if [[ "$current_branch" != "main" && "$current_branch" != "master" ]]; then
        VALIDATION_ERROR="branch is neither main nor master: $repository_dir ($current_branch)"
        return 1
    fi

    if ! upstream_branch="$("$git_bin" -C "$repository_dir" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
        VALIDATION_ERROR="upstream is not configured: $repository_dir"
        return 1
    fi
    if [[ "$upstream_branch" != "origin/$current_branch" ]]; then
        VALIDATION_ERROR="unexpected upstream: $repository_dir ($upstream_branch)"
        return 1
    fi

    if ! origin_url="$("$git_bin" -C "$repository_dir" remote get-url origin 2>/dev/null)"; then
        VALIDATION_ERROR="origin is not configured: $repository_dir"
        return 1
    fi

    origin_repository_dir="$(resolve_repository_dir "$origin_url")"
    lookup_result=$?
    if (( lookup_result != 0 )); then
        VALIDATION_ERROR="origin does not resolve to a unique ghq repository: $repository_dir"
        return 1
    fi
    if [[ "$origin_repository_dir" != "$repository_dir" ]]; then
        VALIDATION_ERROR="origin does not match the listed repository: $repository_url"
        return 1
    fi

    if ! ahead_count="$("$git_bin" -C "$repository_dir" rev-list --count '@{upstream}..HEAD')" ||
        [[ "$ahead_count" != <-> ]]; then
        VALIDATION_ERROR="failed to compare HEAD with upstream: $repository_dir"
        return 1
    fi
    if (( ahead_count > 0 )); then
        VALIDATION_ERROR="local commits would be retained: $repository_dir ($ahead_count commit(s))"
        return 1
    fi

    return 0
}

update_repository() {
    local repository_url="$1"
    local repository_dir
    local lookup_result
    local before_head=""
    local after_head
    local upstream_head
    local is_new_repository=0

    repository_dir="$(resolve_repository_dir "$repository_url")"
    lookup_result=$?

    case "$lookup_result" in
        0)
            if ! validate_repository "$repository_dir" "$repository_url"; then
                log "SKIP" "$repository_url: $VALIDATION_ERROR" >&2
                return "$SKIP_RESULT"
            fi
            if ! before_head="$("$git_bin" -C "$repository_dir" rev-parse HEAD)"; then
                log "ERROR" "$repository_url: failed to read HEAD" >&2
                return 1
            fi
            ;;
        3)
            is_new_repository=1
            ;;
        1|4)
            log "ERROR" "$repository_url: failed to resolve a unique ghq repository" >&2
            return 1
            ;;
        *)
            log "ERROR" "$repository_url: unexpected lookup result ($lookup_result)" >&2
            return 1
            ;;
    esac

    if (( is_new_repository )); then
        log "INFO" "cloning $repository_url"
    else
        log "INFO" "updating $repository_url"
    fi

    if ! "$ghq_bin" get --update -- "$repository_url"; then
        log "ERROR" "$repository_url: ghq update failed" >&2
        return 1
    fi

    repository_dir="$(resolve_repository_dir "$repository_url")"
    lookup_result=$?
    if (( lookup_result != 0 )); then
        log "ERROR" "$repository_url: repository was not found after ghq update" >&2
        return 1
    fi

    if ! validate_repository "$repository_dir" "$repository_url"; then
        log "ERROR" "$repository_url: invalid state after ghq update: $VALIDATION_ERROR" >&2
        return 1
    fi

    if ! after_head="$("$git_bin" -C "$repository_dir" rev-parse HEAD)" ||
        ! upstream_head="$("$git_bin" -C "$repository_dir" rev-parse '@{upstream}')"; then
        log "ERROR" "$repository_url: failed to verify updated revisions" >&2
        return 1
    fi
    if [[ "$after_head" != "$upstream_head" ]]; then
        log "ERROR" "$repository_url: HEAD does not match upstream after update" >&2
        return 1
    fi

    if (( is_new_repository )); then
        log "OK" "$repository_url: cloned at $after_head"
    elif [[ "$before_head" == "$after_head" ]]; then
        log "OK" "$repository_url: already up to date at $after_head"
    else
        log "OK" "$repository_url: updated from $before_head to $after_head"
    fi

    return 0
}

if (( $# > 1 )); then
    print -u2 -- "Usage: ${0:t} [repository-list]"
    exit 64
fi

typeset -r repository_list="${1:-$DEFAULT_REPOSITORY_LIST}"
typeset ghq_bin="${AI_LIBRARIES_GHQ_BIN:-${commands[ghq]:-}}"
typeset git_bin="${AI_LIBRARIES_GIT_BIN:-${commands[git]:-}}"

if [[ -z "$ghq_bin" || ! -x "$ghq_bin" ]]; then
    print -u2 -- "ghq was not found in PATH"
    exit 69
fi
if [[ -z "$git_bin" || ! -x "$git_bin" ]]; then
    print -u2 -- "git was not found in PATH"
    exit 69
fi
if [[ ! -r "$repository_list" ]]; then
    print -u2 -- "Repository list is not readable: $repository_list"
    exit 66
fi

typeset repository_url
integer total_count=0
integer success_count=0
integer skipped_count=0
integer failure_count=0
integer update_result

log "INFO" "starting repository update from $repository_list"

while IFS= read -r repository_url || [[ -n "$repository_url" ]]; do
    repository_url="${repository_url%$'\r'}"
    repository_url="${repository_url##[[:space:]]#}"
    repository_url="${repository_url%%[[:space:]]#}"

    [[ -z "$repository_url" || "$repository_url" == \#* ]] && continue

    (( total_count += 1 ))
    update_repository "$repository_url"
    update_result=$?

    case "$update_result" in
        0)
            (( success_count += 1 ))
            ;;
        "$SKIP_RESULT")
            (( skipped_count += 1 ))
            ;;
        *)
            (( failure_count += 1 ))
            ;;
    esac
done < "$repository_list"

if (( total_count == 0 )); then
    log "ERROR" "repository list contains no URLs" >&2
    exit 1
fi

log "INFO" "summary: total=$total_count success=$success_count skipped=$skipped_count failed=$failure_count"

if (( skipped_count > 0 || failure_count > 0 )); then
    exit 1
fi

exit 0
