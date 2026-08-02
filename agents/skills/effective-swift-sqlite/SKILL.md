---
name: effective-swift-sqlite
description: sqlite-data と swift-structured-queries を使って、Swift の SQLite 実装を効果的に最適化・レビューするガイド。特に fetchAll 後のメモリ側 filter/sort/map を where/order/select に置き換えて DB に押し込み、必要な行と列だけを取得する。さらに、ループで1件ずつ insert している書き込みを一括 insert にまとめて SQL 実行回数を減らす。Repository 実装、既存クエリの性能改善、SQL 生成の見直し、インデックス設計確認を行うときに使う。
---

# Effective Swift SQLite

## 目的
- `sqlite-data` と `swift-structured-queries` で、Repository のクエリを「全件取得して Swift 側で整形」から「DB 側で絞り込み・並び替え・射影」へ寄せる。
- 挙動を維持したまま、I/O 量・メモリ使用量・CPU 負荷を下げる。
- 書き込み時の SQL 発行回数を減らし、トランザクション内オーバーヘッドを抑える。

## 基本ワークフロー
1. 既存クエリで `fetchAll(db)` の後に `filter` / `sorted` / `map` をしていないか確認する。
2. 絞り込みを `where`、並び替えを `order(by:)`、必要列抽出を `select` に移し、SQL 側で処理する。
3. `insert` をループで複数回実行していないか確認し、一括 `insert` へまとめられるか判断する。
4. 返り値の順序・重複・型を既存仕様と一致させる。
5. `WHERE` と `ORDER BY` に対応するインデックスを確認し、必要なら追加する。
6. 変更後にビルドと既存テストを実行し、結果整合性を確認する。

## 推奨パターン

### 1) フィルタ・ソート・射影を SQL に押し込む
避ける:
```swift
let rows = try ActivityTagRow.fetchAll(db)
return rows
  .filter { $0.activityID == activityID }
  .sorted { $0.position < $1.position }
  .map(\.tagID)
```

推奨:
```swift
try ActivityTagRow
  .where { $0.activityID.eq(activityID) }
  .order(by: \.position)
  .select(\.tagID)
  .fetchAll(db)
```

### 2) 必要な列だけを取得する
- 行全体が不要なら `select` で列を限定する。
- 例: `UUID` 配列が欲しいなら `select(\.tagID)` を使う。

### 3) 複数条件を result builder で書く
```swift
try ActivityTagRow
  .where {
    $0.activityID.eq(activityID)
    $0.position.gte(0)
  }
  .fetchAll(db)
```

ただし、`.join`で複数のRowを結合する場合は、クロージャに`$0`や`$1`と書くと対象が分かりにくい。
なので、その場合だけクロージャの引数名を指定する。例えば、`ActivityTagRow`であれば`Row`を取り除いて`activityTag`とする。

### 4) 取得件数が不要に大きい場合は `limit` を使う
- UI の一覧先頭のみ必要なケースでは `limit` を追加する。

### 5) 書き込みは一括 `insert` を優先する
避ける:
```swift
for row in rows {
  try ActivityTagRow.insert { row }.execute(db)
}
```

推奨:
```swift
guard !rows.isEmpty else { return }
try ActivityTagRow.insert { rows }.execute(db)
```

### 6) `update` 文では `#bind()` で値をラップする
Swift 6.3 / Xcode 26.4 以降、`update` クロージャ内での値の代入には `#bind()` マクロが必須。

避ける:
```swift
try ActivityRow
  .find(activityID)
  .update {
    $0.lastSelectedAt = tappedAt
  }
  .returning(\.self)
  .fetchOne(db)
```

推奨:
```swift
try ActivityRow
  .find(activityID)
  .update {
    $0.lastSelectedAt = #bind(tappedAt)
  }
  .returning(\.self)
  .fetchOne(db)
```

### 7) 比較は `eq` / `neq` / `is` / `isNot` メソッドを使う
`==` と `!=` 演算子は `unavailable`。値の比較には `eq` / `neq`、NULL チェックには `is` / `isNot` を使う。
`<` / `>` / `<=` / `>=` は引き続き演算子が使えるが、`lt` / `gt` / `lte` / `gte` メソッドも利用可能。

```swift
// 値の比較
.where { $0.activityID.eq(activityID) }

// NULL チェック
.where { $0.lastSelectedAt.is(nil) }
.where { $0.lastSelectedAt.isNot(nil) }

// IN 句
.where { $0.id.in(tagIDs) }

// 大小比較（演算子でもメソッドでもよい）
.where { $0.position.gte(0) }
```

## インデックス設計の実務ルール
- `where` だけを使うなら、その列のインデックスを優先する。
- `where + order(by:)` を使うなら、条件と並び順に沿った複合インデックスを検討する。
- 例: `where { $0.activityID.eq(id) }` + `order(by: \.position)` なら `(activityID, position)` を候補にする。

## レビュー観点
- `fetchAll` 後の Swift 側 `filter/sorted/map` を不要にしているか。
- 返却順序が仕様通りか（`order(by:)` の明示があるか）。
- `select` で不要列を取っていないか。
- 同一処理で `insert` をループ実行していないか（一括 `insert` へまとめられるか）。
- 既存の一意制約・外部キー制約と矛盾していないか。
- 読み取りは `database.read`、書き込みは `database.write` に分離されているか。
- `==` / `!=` 演算子を使っていないか（`eq` / `neq` / `is` / `isNot` メソッドに置き換え）。
- `update` クロージャ内の値代入に `#bind()` を使っているか。

## 適用時の注意
- テーブル全件が本当に必要な集計処理では、無理に分割しない。
- 最適化後も可読性が下がる場合は、クエリを小さな静的ヘルパーへ切り出して意図を残す。
