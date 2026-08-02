#!/usr/bin/env perl
use utf8;
use strict;
use warnings;
binmode(STDOUT, ":encoding(UTF-8)");
binmode(STDERR, ":encoding(UTF-8)");

# japanese-writing-rules 表記チェッカー
#
# Markdownファイルの地の文(コードブロック・インラインコードを除外)を対象に、
# japanese-writing-rules への違反を検出する。
#
# 使い方:
#   perl check-writing-rules.pl <file.md> [file2.md ...]
#
# 終了コード: 違反あり=1 / 違反なし=0 / 引数なし=2
#
# 検出する違反:
#   - 全角スペース (U+3000)
#   - 全角丸括弧 （ ）
#   - 全角数字 ０-９
#   - 全角英字 Ａ-Ｚ ａ-ｚ
#   - その他の全角記号 ＃ ＆ ： ／ など(全角の ！ ？ は除く)
#   - 半角の ! または ?(日本語の文では全角の ！ ？ を使う)
#   - 日本語と英数字・記号・コードの境界に入った半角スペース
#   - 強調するための ** (行頭の水平線 *** は対象外)
#
# 既知の限界:
#   - Markdownテーブル(| 区切り)のセル内テキストは境界スペース検査の対象外
#     (セル区切りのスペースの誤検出を避けるため)

if (!@ARGV) {
    print STDERR "usage: perl check-writing-rules.pl <file.md> [more files...]\n";
    exit 2;
}

# 日本語の文字(ひらがな・カタカナ・CJK統合漢字・拡張A)
my $JP = qr/[\x{3040}-\x{30FF}\x{3400}-\x{4DBF}\x{4E00}-\x{9FFF}]/;

my $total = 0;
for my $path (@ARGV) {
    $total += check_file($path);
}
exit($total > 0 ? 1 : 0);

sub check_file {
    my ($path) = @_;
    open(my $fh, "<:encoding(UTF-8)", $path) or do {
        print STDERR "cannot open: $path\n";
        return 0;
    };

    my $in_fence = 0;
    my $in_front = 0;
    my @issues;

    while (my $line = <$fh>) {
        my $n = $.;

        # YAMLフロントマター(先頭の --- から次の --- まで)は対象外
        if ($n == 1 && $line =~ /^---\s*$/) { $in_front = 1; next; }
        if ($in_front) {
            $in_front = 0 if $line =~ /^---\s*$/;
            next;
        }

        # コードフェンス(``` または ~~~)でトグルし、ブロック内は対象外
        if ($line =~ /^\s*(?:```|~~~)/) { $in_fence = 1 - $in_fence; next; }
        next if $in_fence;

        my $t = $line;
        chomp $t;
        next if $t eq '';

        # 幅チェック用: インラインコードの中身を除去(コード内の記号を誤検出しない)
        my $scan = $t;
        $scan =~ s/`[^`]*`//g;

        # 強調するための ** は禁止。[*_]+ の除去前に検査する。
        # 行頭の水平線(*** など)はマーカーであり強調ではないので対象外。
        push @issues, [$n, "強調の**",       $t] if $scan !~ /^\s*\*{3,}\s*$/ && $scan =~ /\*\*/;

        $scan =~ s/[*_]+//g;

        push @issues, [$n, "全角スペース",   $t] if $scan =~ /\x{3000}/;
        push @issues, [$n, "全角丸括弧",     $t] if $scan =~ /[\x{FF08}\x{FF09}]/;
        push @issues, [$n, "全角数字",       $t] if $scan =~ /[\x{FF10}-\x{FF19}]/;
        push @issues, [$n, "全角英字",       $t] if $scan =~ /[\x{FF21}-\x{FF3A}\x{FF41}-\x{FF5A}]/;

        # 上記に記載のない記号も半角を使う: 全角形(FF01-FF5E)のうち、
        # 全角で正しい ！(FF01)？(FF1F)と、個別チェック済みの （）数字 英字 を除く全角記号。
        # 全角の通貨記号など(FFE0-FFE6)も対象。波ダッシュ 〜(U+301C)は日本語の記号なので対象外。
        push @issues, [$n, "全角記号",       $t] if $scan =~ /[\x{FF02}-\x{FF07}\x{FF0A}-\x{FF0F}\x{FF1A}-\x{FF1E}\x{FF20}\x{FF3B}-\x{FF40}\x{FF5B}-\x{FF5E}\x{FFE0}-\x{FFE6}]/;

        push @issues, [$n, "半角の!や?",     $t] if $scan =~ /[\x{0021}\x{003F}]/;

        # ラベルとコロン: 日本語の直後の半角コロンは、後ろに半角スペースを1つ置く。
        # コロンの直後が文字か数字(スペースでない)なら違反。
        # 時刻 21:59 やURLなど、日本語以外の直後のコロンは対象外。
        push @issues, [$n, "コロンの後に半角スペースが必要", $t] if $scan =~ /$JP:(?=[\p{L}\p{N}])/;

        # 境界スペース用: インラインコードを非日本語1文字に置換し、
        # 行頭のMarkdownマーカー(見出し/引用/リスト/番号)とインデントを除去
        my $body = $t;
        $body =~ s/`[^`]*`/X/g;
        $body =~ s/^\s+//;
        $body =~ s/^(?:#{1,6}|>|[-*+]|\d+\.)\s+//;
        $body =~ s/[*_]+//g;

        # テーブル行(| 区切り)は境界スペース検査の対象外
        unless ($t =~ /^\s*\|/) {
            # 半角スペース+日本語のうち、コロン直後のスペース(ラベル: 説明)は許容する
            if ($body =~ /$JP / or $body =~ /(?<!:) $JP/) {
                push @issues, [$n, "日本語に隣接する半角スペース", $t];
            }
        }
    }
    close($fh);

    if (@issues) {
        print "=== $path : ", scalar(@issues), " 件の違反 ===\n";
        for my $i (@issues) {
            printf "  L%-4d [%s] %s\n", $i->[0], $i->[1], $i->[2];
        }
    } else {
        print "=== $path : 違反なし ===\n";
    }
    return scalar(@issues);
}
