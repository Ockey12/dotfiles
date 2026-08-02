# Action Boundaries

## Summary
Action Boundaries は「どの Action を、どこから送ってよいか」を明確にする設計方針。

TCA では `Action` が feature の API なので、UI 起点イベント、内部イベント、親通知イベントを分離すると次の効果がある。
- `Reducer.body`を読みやすくなる
- View が内部 Action を誤って送る事故を防げる
- 親子連携の経路が明確になる
- テストで境界を検証しやすくなる

## Boundary Categories
- `view`: ユーザー操作、View ライフサイクル。
- `internal`: Effect 応答、タイマー、通知など UI 非起点イベント。
- `delegate`: 子から親へ伝えるイベント。
- `destination` / `path`: 画面遷移イベント。
- `binding`: View との双方向バインディング。

## Why `ViewAction` Matters
TCA の `ViewAction` と `@ViewAction(for:)` を使うと、View から送れる Action を `Action.View` に制限できる。

`@ViewAction` は View に `send(...)` ヘルパーを生成し、`store.send` 直叩きには警告を出すため、境界違反を早期に検出しやすい。

## Adoption Steps
1. `Action` を `ViewAction` 準拠にし、`case view(View)` を追加する。
2. View 起点の case を `Action.View` に移す。
3. View に `@ViewAction(for: Feature.self)` を付ける。
4. View の `store.send(.view(...))` を `send(...)` に置き換える。
5. Effect 応答を `internal`、親通知を `delegate` に寄せる。
6. 親は `destination(.presented(...delegate...))` を受ける。

## Notes For Reviews
- View が `internal`/`delegate` を直接送っていないか。
- 親が子の `view` を直接読んでいないか。
- `Reducer.body`の switch をカテゴリ単位で追えるか。
- 命名から起点が分かるか（`onTapped...`, `...Response`, `did...`）。

## Sources
- Merowing, "A better way to separate view actions from business logic in The Composable Architecture"  
  https://www.merowing.info/the-composable-architecture-best-practices/
- Point-Free discussion: "Action names and separation in bigger features" (#1440)  
  https://github.com/pointfreeco/swift-composable-architecture/discussions/1440
- TCA source: `ViewAction` protocol  
  https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Observation/ViewAction.swift
- TCA source: `@ViewAction(for:)` macro docs  
  https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Macros.swift
- TCA migration guide (v1.7): View actions section  
  https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.7.md
