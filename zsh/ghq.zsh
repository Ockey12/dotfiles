# ghqで管理しているディレクトリをfzfで表示して、選択したディレクトリに移動する
gcd() {
  local dir
  dir="$(ghq list --full-path | fzf)" || return 0

  [[ -n "$dir" ]] && cd "$dir"
}
