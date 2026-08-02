---
name: effective-sqlite-data
description: sqlite-data と swift-structured-queries を使う Swift アプリで、Repository / LocalDataSource / Database の責務分離と、クエリのアンチパターン回避を設計・レビューするガイド。レイヤー構造の維持、LocalDataSource の集約単位設計、Row と migration の Database モジュール集約、fetchAll 後の Swift 側処理の SQL 押し込み、一括 insert への置き換え、インデックス設計を扱う。ローカルDB設計、永続化レイヤー整理、既存 LocalDataSource の責務見直し時に使う。
---

# Effective SQLite Data

## 目的
- `sqlite-data` と `swift-structured-queries` を使う永続化コードで、責務境界を崩さずに拡張しやすい構造へ寄せる。
- `UI(ViewModelやReducer) -> Repository -> LocalDataSource -> Database(Row/@Table/migration)` の依存方向を維持する。
- LocalDataSource 間依存を避けつつ、集約の保存・復元に必要な複数テーブル参照は許容する。
- LocalDataSource 内のクエリで、不要なデータ転送・メモリ使用・SQL 発行回数を減らす。

## アーキテクチャ

### 1) 依存方向
- `UI(ViewModelやReducer) -> Repository`
- `Repository -> LocalDataSource / RemoteDataSource`
- `LocalDataSource -> Database module`

ただし、複数の`Repository`を使って複雑な機能を実装する場合は、`UseCase`層を実装して良い。
その場合の依存関係は、`UI -> UseCase -> Repository -> LocalDataSource / RemoteDataSource  (->  Database)`になる。

避ける:
```swift
EntityLocalDataSource -> RelatedEntityLocalDataSource
ReportLocalDataSource -> AssignmentLocalDataSource
```

推奨:
```swift
// LocalDataSource は Database モジュールに直接依存する。
// 集約復元に必要なら、複数の Database モジュールを参照してよい。
EntityLocalDataSource -> EntityDatabase
EntityLocalDataSource -> LabelDatabase
EntityLocalDataSource -> EntityLabelAssignmentsDatabase
```

### 2) Repository の責務
- Repository は UI 層(ViewModel や Reducer)から見たユースケース窓口にする。
- local / remote の切り替えや二重保存は Repository に閉じる。
- Repository 自体はビジネスロジックを持たず、LocalDataSource（将来は RemoteDataSource も）に委譲する。

### 3) LocalDataSource の粒度
- LocalDataSource は集約単位に作る。テーブル単位では作らない。
- LocalDataSource は他の LocalDataSource に依存しない。同じレイヤーの横依存を避ける。
- 別集約の取得や保存が必要でも、他 LocalDataSource を呼ばず、自分で必要テーブルを直接読む。
- 中間テーブルは独立した集約として扱わず、必要な集約側 LocalDataSource が直接扱う。

例:
- `replaceAssignedTagIDs(activityID, tagIDs)` は `ActivityLocalDataSource` が担当
- タグ割り当ての中間テーブル `activity_tag_assignments` も `ActivityLocalDataSource` が直接操作する

### 4) Database モジュールの責務
- migration を持つ。
- `@Table` の Row 型を持つ。
- LocalDataSource から参照される Row 型を export する。
- Row 型はドメインモデルとの相互変換メソッドを持つ。

例:
- `ActivityDatabase` に `ActivityRow` と migration
- `TagDatabase` に `TagRow` と migration
- `ActivityAndTagAssignmentsDatabase` に `ActivityTagRow` と migration

### 5) Query 層の判断基準
- `sqlite-data` / `structured-queries` が十分に高水準なので、最初から汎用 Query 層を作らない。
- 単純 CRUD は LocalDataSource に直書きする。
- 同一 query の再利用や複雑な read model 構築が増えても、まずは LocalDataSource 内の private helper で止める。
- 共有 Query 層を導入するのは、変更漏れや可読性低下が継続的に発生してからにする。

## クエリの設計方針

### fetchAll 後の Swift 側処理を SQL に押し込む
`fetchAll` の後に Swift 側で `filter` / `sorted` / `map` をしている場合、`where` / `order` / `select` に置き換えて SQL 側で処理する。行全体が不要なら `select` で列を限定する。

### 書き込みは一括 insert にまとめる
`insert` をループで1件ずつ実行している場合、配列を渡す一括 `insert` に置き換えて SQL 発行回数を減らす。

### インデックス設計
- `where` だけを使うなら、その列のインデックスを優先する。
- `where` + `order(by:)` を使うなら、条件と並び順に沿った複合インデックスを検討する。
- 例: `where { $0.activityID.eq(id) }` + `order(by: \.position)` なら `(activityID, position)` を候補にする。

## エラーハンドリング

### DB制約違反はDBに判定させる
- 主キー、一意性、外部キー、`NOT NULL`など、DBで表現できる整合性ルールはmigrationで制約として定義する。
- Swift側で事前に`SELECT`してから書き込み可否を判断しない。書き込みを直接実行し、DBが制約違反をthrowすることに任せる。
- LocalDataSourceで`DatabaseError.extendedResultCode`をアプリ固有のエラーへ変換し、SQLite固有の詳細を上位層から隠蔽する。
- 変換対象ではないDBエラーは握りつぶさず、そのままthrowする。
- 複数制約に同時に違反し得る場合は、DBが実際にthrowしたエラーを採用し、Swift側で優先順位を推測しない。
- SQLiteの外部キー制約を使う場合は、DB設定で`foreignKeysEnabled`を有効にする。

```swift
enum ChildLocalDataSourceError: Error {
    case idAlreadyExists(UUID)
    case parentNotFound(UUID)
}

func insert(_ row: ChildRow, into db: Database) throws {
    do {
        try ChildRow.insert {
            row
        }
        .execute(db)
    } catch let error as DatabaseError
        where error.extendedResultCode == .SQLITE_CONSTRAINT_PRIMARYKEY {
        throw ChildLocalDataSourceError.idAlreadyExists(row.id)
    } catch let error as DatabaseError
        where error.extendedResultCode == .SQLITE_CONSTRAINT_FOREIGNKEY {
        throw ChildLocalDataSourceError.parentNotFound(row.parentID)
    }
}
```

### 書き込み結果から制約違反を推測しない
書き込みクエリの返り値が0件、または`INSERT ... RETURNING`を`fetchOne`した結果が`nil`という事実は、行が書き込まれなかったことしか示さない。そこから`notFound`や`alreadyExists`などの制約違反の原因を推測しない。

特に`INSERT ... SELECT`の入力側が0件になると、書き込みが行われず、制約も評価されない。`nil`から原因を推測すると、同じ値を直接`INSERT`した場合にDBが返す制約エラーとは異なるアプリ固有エラーを返す可能性がある。制約違反を判定する書き込みでは、DBに書き込みを実行させ、DBがthrowした制約エラーを変換する。

## レビュー観点

### アーキテクチャ
- UI 層(ViewModel や Reducer)が LocalDataSource を直接参照していないか。
- Repository が local / remote の詳細を隠蔽しているか。
- LocalDataSource が他 LocalDataSource に依存していないか。
- Row 型が Database モジュールに集約されているか。
- LocalDataSource 内で `@Table` をその場定義していないか。
- Query 層を追加せずに済む箇所まで抽象化していないか。

### クエリ
- `fetchAll` 後の Swift 側 `filter` / `sorted` / `map` を SQL に置き換えられるか。
- 返却順序が仕様通りか（`order` の明示があるか）。
- `select` で不要列を取得していないか。
- 同一処理で `insert` をループ実行していないか（一括 `insert` へまとめられるか）。
- 既存の一意制約・外部キー制約と矛盾していないか。
- DBの制約エラーは`ResultCode`からエラーを生成してthrowしているか(返り値が0個やnullなことをSwift側でエラーとして解釈するのを避けているか)。

## 適用時の注意
- 集約復元のために複数テーブルへ依存することと、LocalDataSource 間依存は別物として扱う。
- レイヤー追加は保守コストなので、危険を減らす目的が明確でない限り増やさない。
- テーブル全件が本当に必要な集計処理では、無理に SQL で分割しない。
- 最適化後も可読性が下がる場合は、クエリを小さな private helper へ切り出して意図を残す。
