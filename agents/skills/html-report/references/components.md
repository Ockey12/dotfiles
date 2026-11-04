# コンポーネント

本文断片で使えるのは、このファイルに載っているコンポーネントだけである。ここにない要素やclassを新しく作らない。表現したい内容が当てはまらない場合は、最も近いコンポーネントで代用する。

すべての開始タグは必ず閉じる(`</p>`や`</li>`も省略しない)。`style`属性、`<style>`、`<script>`は書かない。`scripts/build.py`がこれらの規約を検査する。

## 目次

- [ページヘッダー](#ページヘッダー)
- [要約](#要約)
- [見出し](#見出し)
- [段落とリスト](#段落とリスト)
- [ToDoリスト](#todoリスト)
- [コールアウト](#コールアウト)
- [タグ](#タグ)
- [表](#表)
- [コード](#コード)
- [トグル](#トグル)
- [引用](#引用)
- [段組み](#段組み)
- [図](#図)
- [出典](#出典)
- [補足テキストと区切り線](#補足テキストと区切り線)
- [自動で付くもの](#自動で付くもの)

## ページヘッダー

本文断片の先頭に必ず1つ置く。`<title>`はページタイトルから自動で設定される。

```html
<header class="page-header">
  <div class="page-icon">🔍</div>
  <h1 class="page-title">ObservableObjectから@Observableへの移行調査</h1>
  <dl class="props">
    <dt>作成日</dt><dd>2026-11-05</dd>
    <dt>種類</dt><dd><span class="tag blue">調査</span></dd>
    <dt>対象</dt><dd>SwiftUIアプリの状態管理</dd>
    <dt>ステータス</dt><dd><span class="tag green">完了</span></dd>
  </dl>
</header>
```

- アイコンはレポートの種類で決める。調査は🔍、比較は⚖️、障害調査は🐛、設計は📐、まとめは📝。
- プロパティは「作成日、種類、対象、ステータス」の順に、この4つを基本とする。ステータスが意味を持たないレポートでは省略してよい。
- 作成日は`YYYY-MM-DD`で書く。
- 種類はタグで書く。色は調査が`blue`、比較が`purple`、障害調査が`red`、設計が`orange`、まとめが`gray`。
- ステータスは`完了`(green)、`進行中`(blue)、`要確認`(yellow)のいずれか。

## 要約

ページヘッダーの直後に、灰色のコールアウトで要約を置く。最初の段落は「結論: 」から始め、結論を1〜2文で書く。根拠や要点は3項目程度の箇条書きにする。

```html
<div class="callout">
  <p>結論: 最小対応OSがiOS 17以降なら、モデル型を1つずつ@Observableへ移行できる。</p>
  <ul>
    <li>Viewは<code>body</code>で読んだプロパティが変わったときだけ更新される</li>
    <li>ObservableObjectと混在させたまま、段階的に移行できる</li>
  </ul>
</div>
```

## 見出し

使える見出しは`<h2>`(セクション)と`<h3>`(サブセクション)だけである。`<h2>`と`<h3>`はトップレベルに置く。`<h3>`だけは段組みの列の中にも置ける。見出しに絵文字や番号を付けない。

```html
<h2>調査結果</h2>
<h3>更新の仕組みの違い</h3>
```

## 段落とリスト

```html
<p>1段落には1つの論点だけを書く。</p>

<ul>
  <li>順序のない項目</li>
  <li>入れ子は2段まで
    <ul>
      <li>子の項目</li>
    </ul>
  </li>
</ul>

<ol>
  <li>手順や順位のある項目</li>
  <li>2つ目の項目</li>
</ol>
```

リンクは`<a href="https://...">リンクテキスト</a>`と書く。外部リンクには`target`が自動で付く。

## ToDoリスト

次のアクションや確認事項に使う。完了した項目には`class="done"`を付ける。

```html
<ul class="todo">
  <li class="done">移行ガイドを確認する</li>
  <li>最小対応OSを確認する</li>
</ul>
```

## コールアウト

アイコンと背景色は種類ごとに固定されている。アイコンは自動で表示されるため書かない。中身は必ず`<p>`やリストで囲む。

| class | アイコン | 用途 |
| --- | --- | --- |
| `callout` | 💡 | 要約、補足 |
| `callout info` | ℹ️ | 前提、背景情報 |
| `callout success` | ✅ | 結論、推奨案 |
| `callout warning` | ⚠️ | 注意点、制約 |
| `callout danger` | 🚨 | 重大なリスク、破壊的な変更 |

```html
<div class="callout warning">
  <p>段階移行中は、型ごとにViewの更新条件が異なる。</p>
</div>
```

コールアウトは1セクションに1つまでを目安にする。多用すると区別の意味がなくなる。

## タグ

Notionのセレクトのような小さなラベル。状態、評価、分類を短い語で示す。色は意味で決め、レポートをまたいで同じ意味に同じ色を使う。

| 色 | 意味 |
| --- | --- |
| `green` | 推奨、採用、対応、完了 |
| `yellow` | 条件付き、要確認、保留 |
| `red` | 非推奨、不採用、非対応、高リスク |
| `blue` | 情報、進行中、必須 |
| `gray` | 中立、対象外、未定 |
| `purple`、`pink`、`brown`、`orange` | 意味を持たない分類(カテゴリの区別)にだけ使う |

```html
<span class="tag green">推奨</span>
<span class="tag red">非対応</span>
```

`tag`だけを付けると`gray`になる。表の中で「対応/非対応」や「○/×」を示すときも、記号や絵文字ではなくタグを使う。

## 表

3つ以上の項目を2つ以上の観点で比べるときは、文章や箇条書きではなく表にする。1行目は必ず`<th>`の見出し行にする。セルの中は短い語句にし、長い説明は表の外に書く。

```html
<table>
  <thead>
    <tr><th>観点</th><th>案A</th><th>案B</th></tr>
  </thead>
  <tbody>
    <tr><td>対応OS</td><td>iOS 13以降</td><td>iOS 17以降</td></tr>
    <tr><td>評価</td><td><span class="tag yellow">条件付き</span></td><td><span class="tag green">推奨</span></td></tr>
  </tbody>
</table>
```

表は内容の幅に合わせて表示され、本文の幅を超える場合は横にスクロールする。

## コード

コードブロックは`<pre>`と`<code>`で書き、`data-lang`に言語名を小文字で書く。言語名はブロックの左上に表示される。コード中の`<`、`>`、`&`は必ず`&lt;`、`&gt;`、`&amp;`にエスケープする。シンタックスハイライトはしない。

```html
<pre data-lang="swift"><code>@Observable class Library {
    var books: [Book] = []
}

let names: Array&lt;String&gt; = []</code></pre>
```

- `data-lang`の例: `swift`、`bash`、`json`、`yaml`、`diff`、`text`
- 移行前と移行後を比べるときは、1つのブロックの中で`// 移行前`、`// 移行後`のコメントで区切る
- インラインコードは`<code>`だけで書く。API名、型名、ファイルパス、コマンドに使う
- キー操作は`<kbd>⌘</kbd> <kbd>K</kbd>`のように書く

## トグル

長いログ、詳細なデータ、補足的な説明など、全員が読む必要のない内容を折りたたむ。`<summary>`には中身が分かる短い文を書く。中身は`<p>`などのブロックで囲む。

```html
<details>
  <summary>iOS 16以前もサポートする場合</summary>
  <p>Perceptionライブラリを使う。</p>
</details>
```

最初から開いておく場合は`<details open>`と書く。

## 引用

ドキュメントや仕様の原文をそのまま引用するときに使う。引用の直後に出典を付ける。

```html
<blockquote>
  <p>Your app can mix data model types that use different observation systems.</p>
</blockquote>
```

## 段組み

2つまたは3つの観点を横に並べて見比べるときに使う。列は`class`のない`<div>`にする。画面の幅が狭いと縦に並ぶ。項目ごとの比較なら段組みではなく表を使う。

```html
<div class="columns">
  <div>
    <h3>移行する利点</h3>
    <ul><li>不要な再描画が減る</li></ul>
  </div>
  <div>
    <h3>移行で気をつけること</h3>
    <ul><li>iOS 17以降が必要になる</li></ul>
  </div>
</div>
```

## 図

画像はスクリーンショットなど、実際に存在するファイルやURLだけに使う。図を新しく描かない(SVGやCanvasは使えない)。構造を示したいときは、表、リスト、`data-lang="text"`のコードブロックで代用する。

```html
<figure>
  <img src="screenshot.png" alt="設定画面のスクリーンショット">
  <figcaption>設定画面</figcaption>
</figure>
```

## 出典

本文中の出典は`<a class="cite" href="#src-1">[1]</a>`で示し、最後のセクション「参考資料」に番号付きリストでまとめる。番号は本文に初めて出てきた順に振る。リンク先は実際に読んだものだけにする。

```html
<p>Viewの<code>body</code>が読んだプロパティだけを追跡する<a class="cite" href="#src-1">[1]</a>。</p>

<h2>参考資料</h2>
<ol class="sources">
  <li id="src-1"><a href="https://developer.apple.com/documentation/swiftui/migrating-from-the-observable-object-protocol-to-the-observable-macro">Migrating from the Observable Object protocol to the Observable macro</a> <span class="muted">developer.apple.com</span></li>
</ol>
```

## 補足テキストと区切り線

- `<span class="muted">`と`<p class="muted">`: 出典のドメイン名、注記など、目立たせたくない補足に使う
- `<hr>`: 話題が大きく切り替わる箇所に使う。セクションの区切りには見出しを使い、`<hr>`は使わない

## 自動で付くもの

以下は`scripts/build.py`が付けるため、本文断片には書かない。

- `<h2>`が4つ以上あるときの目次(最初の`<h2>`の直前に入る)
- `<h2>`と`<h3>`のid(`sec-1`から順に振られる)
- 外部リンクの`target="_blank"`と`rel`
- `<title>`、CSS、`<html>`、`<head>`、`<body>`
