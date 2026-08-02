---
name: effective-composable-architecture
description: The Composable Architecture (TCA) を効果的に使うための設計・レビューガイド。特に ViewAction と Action Boundaries（view/internal/delegate）で Action の責務境界を明確化し、Reducer の可読性・テスタビリティ・親子連携を改善するときに使う。TCA feature の新規実装、既存 feature のリファクタ、コードレビュー、Action 設計の統一、Effect/Dependency/Navigation/Binding パターンの見直し時に利用する。
---

# Effective Composable Architecture

## Overview
TCA feature を「Action 境界が明確で、UI から送れるイベントが制御され、テストしやすい構造」に揃える。

この skill は特に `ViewAction` の導入・運用を中心に扱う。Action 設計の背景は `references/action-boundaries.md` を参照する。

## Workflow
1. 対象 feature の `Action` を、`view` / `internal` / `delegate` / `destination` / `binding` のどれに属するか分類する。
2. View 起点のイベントだけを `Action.View` に寄せ、`Action` を `ViewAction` 準拠にする。
3. View 側に `@ViewAction(for:)` を適用し、`store.send` ではなく `send(...)` を使う。
4. Effect 応答は `internal` に集約し、親への通知は `delegate` に限定する。
5. Navigation (`destination`/`path`) と binding (`binding`) を Action 境界から分離し、Reducer の switch を読みやすく保つ。
6. TestStore で `view -> internal/delegate` の流れを検証する。

## ViewAction With Action Boundaries

### 1) Action を API として扱う
- `Action` は「その feature が外部に公開する操作面」。
- View から送れる Action を制限しないと、UI が内部イベントを直接送れてしまう。
- `ViewAction` + `@ViewAction` で「View が送ってよい Action」を型で制限する。

### 2) 推奨 Action 構造
```swift
public enum Action: ViewAction, BindableAction {
    case view(View)
    case `internal`(Internal)
    case delegate(Delegate)
    case destination(PresentationAction<Destination.Action>)
    case binding(BindingAction<State>)

    @CasePathable
    public enum View {
        case onAppear
        case onTappedSaveButton
    }

    @CasePathable
    public enum Internal {
        case saveResponse(Result<Void, Error>)
    }

    @CasePathable
    public enum Delegate {
        case didSave
    }
}
```

`@Reducer`マクロが、トップレベルの`Action`に自動で`@CasePathable`マクロを付与する。
一方で、ネストしているenumには`@CasePathable`マクロを明示的に付与する必要がある。
Actionの各enumに`@CasePathable`マクロを付与することで、テストにてネストしたenumのcaseをKeyPathと同じように記述できる。

### 3) 境界のルール
- `View`: ユーザー操作、View ライフサイクル（`task`, `onAppear`, ボタン tap など）。
- `Internal`: 非同期処理の結果、タイマー tick、通知受信など「UI 起点でないイベント」。
- `Delegate`: 親 feature に伝えるイベント。子 feature の `View` を親が直接扱う設計を避ける。
- `Destination/Path`: 画面遷移の状態変化。
- `Binding`: フォーム入力などの双方向バインディング。

### 4) View 側の実装ルール
- `@ViewAction(for: Feature.self)` を付与する。
- View では `send(.someViewAction)` を使う。
- `store.send` の使用は禁止。
- Reducer が `Action.View` を受け、必要に応じて `internal` / `delegate` に変換する。
- `BindableAction` を使う状態は、`Binding(get:set:)` を手書きする前に `$store`（例: `$store.name`, `$store.scope(...)`）で接続する。
- `Binding(get:set:)` は TCA の状態導出で表現できない UI 連携がある場合に限定し、通常のフォーム入力では使わない。

## Destination Pattern (汎用)

どのアプリでも「表示トリガーは `view`、sheetやfullScreenCoverなどの子画面の結果受信は `destination(.presented(...))`」に統一すると、責務境界が崩れにくい。

### 1) 親 feature の基本形
```swift
@Reducer
public struct ParentFeature {
    @Reducer
    public enum Destination {
        case childSheet(ChildFeature)
    }

    @ObservableState
    public struct State {
        @Presents var destination: Destination.State?
    }

    public enum Action: ViewAction {
        case view(View)
        case destination(PresentationAction<Destination.Action>)

        @CasePathable
        public enum View {
            case onTappedOpenButton
        }
    }

    public var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .view(.onTappedOpenButton):
                state.destination = .childSheet(.init())
                return .none

            case .destination:
                return .none
            }
        }
        .ifLet(\.$destination, action: \.destination)
    }
}
```

### 2) 子 feature の結果は delegate で閉じる
- 子の確定/キャンセルなど親に返したいイベントは `Action.Delegate` に置く。
- 親は `case .destination(.presented(.childSheet(.delegate(...))))` で結果だけを受ける。

### 3) dismiss 責務の分離
- モーダルを閉じる責務は feature ごとに決めて固定する。
- 代表的な 2 パターン:
  - 子自身が `@Dependency(\.dismiss)` で閉じる。
  - 親が delegate 受信時に `state.destination = nil` をセットする。
- `sheet`/ `fullScreenCover` にキャンセルボタンがあり、要件が「非表示にするだけ」で親状態更新が不要な場合は、子 Reducer 側で `dismiss` を実行する。
- 同一フロー内はどちらか一方に寄せ、二重 dismiss を避ける。

### 4) View 側の接続
- `sheet`/ `fullScreenCover` は `item: $store.scope(state: \.destination?.xxx, action: \.destination.xxx)` で接続する。

### 5) Path との併用ルール
- モーダル系は `destination`、push 系は `path` に分離する。
- 1 feature 内で混在しても責務を分ける。

### 6) テスト観点
- `view` Action で `state.destination` が正しくセットされることを確認する。
- `destination(.presented(...delegate...))` 受信で、親状態更新と dismiss（`destination = nil` または `dismiss`）が期待通りかを確認する。
- キャンセル系イベントが副作用なしで終了することを確認する。

## Effective TCA Practices Beyond ViewAction
- Dependency: `@Dependency` を使い、`Date()` / `UUID()` / 直接クライアント呼び出しを避ける。
- Effect: 副作用は `.run` で起動し、結果は `internal` Action に戻す。
- Parent-child: 子から親へは `delegate` で通知し、親は `destination(.presented(...delegate...))` を処理する。
- Binding: `BindableAction` + `BindingReducer()` を使用し、View は原則 `$store` で bind する（手書き `Binding(get:set:)` は最小化）。
- Navigation: `@Presents` / `StackState` と `ifLet` / `forEach` で状態駆動に統一する。
- Naming: `onTapped...`, `...Response`, `did...` のように起点が分かる命名にする。
  - ユーザー操作に対応するcase名は、"on" + "操作を表す動詞" + "操作対象"にする。

## Review Checklist
- View から送る Action が `view` に限定されている。
- Effect の戻りが `internal` に集約されている。
- 親子連携が `delegate` 経由になっている。
- `destination`/`path`/`binding` が他カテゴリと混ざっていない。
- View の binding が原則 `$store` 経由で、不要な `Binding(get:set:)` が増えていない。
- Reducer の `switch` が Action 境界ごとに読み分けられる。
- TestStore で主要フロー（view -> internal/delegate）を確認している。

## References
- Action Boundaries の背景と ViewAction の設計意図: `references/action-boundaries.md`

## Extension Notes
この skill は継続的に拡張する前提。新しい知見は以下の方針で追記する。
- 実装手順は `SKILL.md` に短く追記する。
- 長い解説や出典は `references/` に分離する。