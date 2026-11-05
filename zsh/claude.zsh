# セッションIDを指定して、Claude Codeの会話をForkして開く
# 2つ目以降の引数はclaudeにそのまま渡す
cfork() {
    if (( $# == 0 )); then
        print -u2 -- 'usage: cfork <session-id> [claude options...]'
        return 1
    fi

    claude --resume "$1" --fork-session "${@:2}"
}
