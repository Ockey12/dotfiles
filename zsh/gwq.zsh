# カレントディレクトリのリポジトリにあるブランチをfzfで表示して、worktreeに追加する
# チェックアウト中のブランチはグレー表示にして選択できないようにする
gwa() {
    local repo_root selected selection_state branch worktree_path

    repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
        print -u2 -- 'gwa: Gitリポジトリ内で実行してください'
        return 1
    }

    selected="$(
        git -C "$repo_root" for-each-ref \
            --sort=refname \
            --format='%(refname:short)%09%(worktreepath)' \
            refs/heads |
        while IFS=$'\t' read -r branch worktree_path; do
            if [[ -n "$worktree_path" ]]; then
                printf 'checked\t%s\t\033[90m%s [チェックアウト中]\033[0m\n' "$branch" "$branch"
            else
                printf 'available\t%s\t%s\n' "$branch" "$branch"
            fi
        done |
        fzf --ansi \
            --delimiter=$'\t' \
            --with-nth=3 \
            --prompt='Add worktree> ' \
            --bind 'enter,double-click:transform:[[ {1} == available ]] && echo accept || echo bell'
    )" || return

    selection_state="${selected%%$'\t'*}"
    [[ "$selection_state" == available ]] || return 1

    selected="${selected#*$'\t'}"
    branch="${selected%%$'\t'*}"
    gwq add -- "$branch"
}

# カレントディレクトリのリポジトリにあるブランチを起点に、新しいブランチとworktreeを作成する
gwa-b() {
    local repo_root base_branch new_branch

    repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
        print -u2 -- 'gwa-b: Gitリポジトリ内で実行してください'
        return 1
    }

    base_branch="$(
        git -C "$repo_root" for-each-ref \
            --sort=refname \
            --format='%(refname:short)' \
            refs/heads |
        fzf --prompt='Base branch> '
    )" || return

    read -r "new_branch?New branch from $base_branch> " || return
    [[ -n "$new_branch" ]] || return

    if ! git -C "$repo_root" check-ref-format --branch "$new_branch" >/dev/null 2>&1; then
        print -u2 -- "gwa-b: 無効なブランチ名です: $new_branch"
        return 1
    fi

    if git -C "$repo_root" show-ref --verify --quiet "refs/heads/$new_branch"; then
        print -u2 -- "gwa-b: ブランチはすでに存在します: $new_branch"
        return 1
    fi

    git -C "$repo_root" branch -- "$new_branch" "$base_branch" || return

    if ! gwq add -- "$new_branch"; then
        print -u2 -- "gwa-b: worktreeを作成できませんでした。ブランチは残しています: $new_branch"
        return 1
    fi
}

# カレントディレクトリのworktreesをfzfで表示して、選択したものを削除する
# ブランチは削除しない
gwd() {
    local selected worktree_path

    selected="$(
        gwq list --json |
        jq -r '.[] | select(.is_main | not) | [.branch, .path] | @tsv' |
        fzf --delimiter=$'\t' --with-nth=1,2
    )" || return

    worktree_path="${selected#*$'\t'}"
    gwq remove -- "$worktree_path"
}

# カレントディレクトリのworktreesをfzfで表示して、選択したものとブランチを削除する
gwd-b() {
    local selected worktree_path

    selected="$(
        gwq list --json |
        jq -r '.[] | select(.is_main | not) | [.branch, .path] | @tsv' |
        fzf --delimiter=$'\t' --with-nth=1,2
    )" || return

    worktree_path="${selected#*$'\t'}"
    gwq remove -b -- "$worktree_path"
}
