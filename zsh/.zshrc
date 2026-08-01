# マシン固有設定
if [[ -f "$HOME/.zshrc.local" ]]; then
  source "$HOME/.zshrc.local"
fi

# ここでzsh設定ファイルを読み込む
source "${${(%):-%N}:A:h}/ghq.zsh"
source "${${(%):-%N}:A:h}/gwq.zsh"

eval "$(starship init zsh)"
