# Child FeatureへActionを送りたい場合の選択肢と判断基準

## 目次

- [位置づけ](#位置づけ)
- [選択肢と判断基準](#選択肢と判断基準)
- [同期State更新の実装](#同期state更新の実装)
- [TCA 1のtrigger境界](#tca-1のtrigger境界)
- [ビルド済みサンプル](#ビルド済みサンプル)
- [キャンセル領域の根拠](#キャンセル領域の根拠)
- [cancelInFlightを付ける場所](#cancelinflightを付ける場所)
- [通常のScopeで使う場合](#通常のscopeで使う場合)
- [Effect.mapを新規設計で使わない](#effectmapを新規設計で使わない)
- [性能と設計の判断](#性能と設計の判断)
- [Featureのreduceを直接呼ばない](#featureのreduceを直接呼ばない)
- [Delegateとの関係](#delegateとの関係)
- [TCA 2への移行](#tca-2への移行)
- [テスト観点](#テスト観点)
- [参照資料](#参照資料)

## 位置づけ

Parent FeatureからChild FeatureのStateを変更したい、またはChild Featureの処理を起動したい場合は、具体的なChild FeatureのActionをすぐに構築せず、先にState、Effect、Dependencyの所有者を決める。この資料では、直接のState更新、同期処理の共有、Effectの所有者の変更、Dependencyの共有、TCA 1の`trigger`を比較し、要件に合う入力方法を選ぶ。

Child Featureの`view`や`internal`を処理の命令として流用しない。

```swift
// 採用しない
return .send(.child(.view(.onTappedRefreshButton)))
return .send(.child(.internal(.refreshResponse(result))))
```

外部からChild Featureの処理を起動する必要がある場合も、先に[選択肢と判断基準](#選択肢と判断基準)で処理とEffectの所有者を決める。Action送信が要件に合う場合だけ`trigger`を選び、実装は[TCA 1のtrigger境界](#tca-1のtrigger境界)に従う。

## 選択肢と判断基準

| 状況 | 選択肢 | Child FeatureのAction送信 |
| --- | --- | --- |
| Parent Featureだけが行うChild FeatureのStateの同期更新 | Parent Featureから直接更新 | 送らない |
| Child FeatureとParent Featureが同じ同期更新を行う | Child FeatureのStateの`mutating`メソッド | 送らない |
| Parent Featureだけが所有する非同期処理 | Parent FeatureのState、Action、Dependency、Effect | 送らない |
| Child Featureだけが所有し、外部起動が不要な非同期処理 | Child Featureの`view`または内部処理 | 送らない |
| 複数Featureが別々にEffectを所有し、同じ処理だけを使う | Dependencyの非同期APIまたは純粋関数を共有 | 送らない |
| Child Feature所有の非同期処理をChild FeatureとParent Featureの両方から起動する | `trigger`候補として下記条件を確認 | 条件を満たす場合だけ送る |

`trigger`を選ぶ前に次を確認する。

1. 処理、応答後の状態更新、Cancellation IDをChild Featureが所有するか。
2. Child Feature自身とParent Featureの両方に開始理由があるか。
3. Parent Feature所有、永続Feature、共有データの所有者への引き上げより、Child Featureへ置く方が自然か。
4. スクロール、ジェスチャー、文字入力、フレーム更新、多数のChild Featureへの細かなAction送信などの高頻度処理ではなく、通信や再読み込みなど意味のある低頻度処理か。
5. Optional、Presentation、Collection、Stack上のChild Featureでは、送信時に対象が存在し、Actionを即座に送れるか。

すべての条件を満たす場合に限り、TCA 1では`Action.trigger(Trigger)`をChild Featureの外部入力境界として定義し、Parent FeatureからそのCaseだけを送る。この`trigger`はTCA 1の公式機能ではなく、TCA 2の公式`@Trigger`への移行意図を表すローカル規約である。条件を説明できない場合は、表に戻ってActionを送らない選択肢を選ぶ。

Child FeatureからParent Featureへ判断を求める通知は逆向きの境界である。[Delegateとの関係](#delegateとの関係)で扱う。

## 同期State更新の実装

この節では、[選択肢と判断基準](#選択肢と判断基準)に示した2つの同期更新パターンを実装する。

### Parent Featureだけが更新する場合

```swift
case let .internal(internalAction):
  switch internalAction {
  case let .childProgressUpdated(progress):
    state.child.progress = progress
    return .none
}
```

この代入だけを隠すParent Feature専用メソッドをChild FeatureのStateへ追加しない。

### Parent FeatureとChild Featureが共有する場合

```swift
extension Child.State {
  mutating func clearSelection() {
    selectedID = nil
  }
}
```

```swift
// Child Feature
case let .view(viewAction):
  switch viewAction {
  case .onTappedClearButton:
    state.clearSelection()
    return .none
  }

// Parent Feature
case let .view(viewAction):
  switch viewAction {
  case .onTappedClearChildSelectionButton:
    state.child.clearSelection()
    return .none
}
```

共有する`mutating`メソッドは同期State更新だけを行い、`Effect`を返さない。非同期処理まで共有する場合は[選択肢と判断基準](#選択肢と判断基準)に戻って処理の所有者を決め直す。

## TCA 1のtrigger境界

[選択肢と判断基準](#選択肢と判断基準)で採用した`Action.trigger(Trigger)`の最小構造は次のとおりである。

```swift
enum Action: ViewAction {
  case view(View)
  case trigger(Trigger)
  case `internal`(Internal)

  @CasePathable
  enum View {
    case onAppear
  }

  @CasePathable
  enum Trigger {
    case refresh
  }

  @CasePathable
  enum Internal {
    case refreshFinished
  }
}
```

Child Feature自身の開始ActionとParent Featureからの`trigger`は、それぞれのAssociated Valueを取り出してから内側で`switch`し、同じFeatureローカルヘルパーを直接呼ぶ。

```swift
case let .view(viewAction):
  switch viewAction {
  case .onAppear:
    return refresh(state: &state)
  }

case let .trigger(triggerAction):
  switch triggerAction {
  case .refresh:
    return refresh(state: &state)
  }
```

次の中継は行わない。

```swift
// 採用しない
case let .view(viewAction):
  switch viewAction {
  case .onAppear:
    return .send(.trigger(.refresh))
  }
```

中継ActionはStoreを余分に通り、TestStoreにも実装詳細として現れる。Featureローカルヘルパーなら、実処理の実装、状態遷移、Cancellation IDを1か所へ集約できる。

## ビルド済みサンプル

次のコードは、前節の`trigger`境界をOptionalなDestinationへ適用したサンプルである。TCA 1.26.0、Swift 6.2、iOS 26.4 Simulator向けにビルド済みである。

```swift
import ComposableArchitecture

struct Content: Identifiable, Sendable {
    let id: String
}

@DependencyClient
struct ContentRepository: Sendable {
    var getAllContents: @Sendable () async throws -> [Content]
}

extension ContentRepository: DependencyKey {
    static var liveValue: Self {
        .init(getAllContents: { [Content(id: "sample")] })
    }
}

extension DependencyValues {
    var contentRepository: ContentRepository {
        get { self[ContentRepository.self] }
        set { self[ContentRepository.self] = newValue }
    }
}

@Reducer
struct Child {
    @ObservableState
    struct State {
        var isRefreshing = false
        var list: IdentifiedArrayOf<Content> = []
    }

    enum Action: ViewAction {
        case view(View)
        case trigger(Trigger)
        case `internal`(Internal)

        @CasePathable
        enum View {
            case onAppear
        }

        @CasePathable
        enum Trigger {
            case refresh
        }

        @CasePathable
        enum Internal {
            case getAllContentsResponse(Result<[Content], any Error>)
        }
    }

    private enum CancelID {
        case refresh
    }

    @Dependency(\.contentRepository) private var contentRepository

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case let .view(viewAction):
                switch viewAction {
                case .onAppear:
                    return refresh(state: &state)
                }

            case let .trigger(triggerAction):
                switch triggerAction {
                case .refresh:
                    return refresh(state: &state)
                }

            case let .internal(internalAction):
                switch internalAction {
                case let .getAllContentsResponse(result):
                    state.isRefreshing = false
                    if case let .success(contents) = result {
                        state.list = .init(uniqueElements: contents)
                    }
                    return .none
                }
            }
        }
    }

    private func refresh(state: inout State) -> Effect<Action> {
        state.isRefreshing = true
        return .run { send in
            await send(.internal(.getAllContentsResponse(Result {
                try await contentRepository.getAllContents()
            })))
        }
        .cancellable(id: CancelID.refresh, cancelInFlight: true)
    }
}

@Reducer
struct Parent {
    @Reducer
    enum Destination {
        case child(Child)
    }

    @ObservableState
    struct State {
        @Presents var destination: Destination.State?
    }

    enum Action: ViewAction {
        case view(View)
        case destination(PresentationAction<Destination.Action>)

        @CasePathable
        enum View {
            case onTappedPresentChildButton
            case onTappedReloadChildButton
        }
    }

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case let .view(viewAction):
                switch viewAction {
                case .onTappedPresentChildButton:
                    state.destination = .child(Child.State())
                    return .none

                case .onTappedReloadChildButton:
                    guard case .child = state.destination else {
                        return .none
                    }
                    return .send(.destination(.presented(.child(.trigger(.refresh)))))
                }

            case .destination:
                return .none
            }
        }
        .ifLet(\.$destination, action: \.destination)
    }
}
```

このサンプルのParent Featureは、Child FeatureのDependency、Response Action、State更新、Cancellation IDを知らない。Parent Featureの`.send`とChild Featureの通信Effectが属するキャンセル領域は、次節で説明する。

## キャンセル領域の根拠

TCA 1.26.0の`PresentationReducer._reduce`は、Child Featureが返す`destinationEffects`とParent Featureが返す`baseEffects`を分ける。Presented ActionではChild Featureを実行し、そのEffectへChild Featureの`navigationIDPath`をDependencyとして設定してから`_cancellable(navigationIDPath:)`で包む。Parent FeatureのEffectは別の`baseEffects`として実行する。

Parent FeatureからChild FeatureのStateのEffect返却メソッドを呼ぶ場合、そのEffectはParent Featureの戻り値なので`baseEffects`になる。将来出力するActionを`.map { .destination(...) }`しても、Action型を変換するだけで通信タスク自体はChild Featureの`destinationEffects`へ移らない。

Parent FeatureからChild Featureの`trigger`を`.send`する場合、最初の`.send`はParent Featureの`baseEffects`、Child Featureが返す通信Effectは`destinationEffects`になる。この分離は次の処理順序で成立する。

処理順序は次のとおりである。

1. Parent FeatureのActionを処理する。
2. Parent Featureの即時`Effect.send`を実行する。
3. StoreへChild Featureの`trigger`が入り直す。
4. `PresentationReducer`がPresented Actionを処理する。
5. Child FeatureがActionを処理する。
6. Child Featureが通信Effectを返す。
7. Child Featureの`navigationIDPath`によって通信Effectが自動キャンセルの対象になる。

TCA 1.26.0の`Effect.cancellable`も`navigationIDPath`をCancellation IDの一部として使う。そのため、Child Feature内で付けた`CancelID.refresh`は対象Child FeatureのIdentityへスコープされる。

Destinationが`nil`になると、PresentationのChild FeatureのEffectは自動キャンセルされる。通常の`Scope`で常に存在するChild Featureには、このPresentation破棄境界はない。

## cancelInFlightを付ける場所

`cancelInFlight`は[ビルド済みサンプル](#ビルド済みサンプル)の`refresh(state:)`のように、Child Featureの実処理を返すEffectへ付ける。

Cancellation IDをFeatureローカルヘルパーのEffectへ集約することで、開始元に関係なく、後から開始した再読み込みが同じChild Feature内の古い処理をキャンセルする。

Parent Featureの即時`.send`へ付けない。

```swift
// 採用しない。即時送信だけが対象で、Child Featureの通信は対象にならない
return .send(.destination(.presented(.child(.trigger(.refresh)))))
  .cancellable(id: ParentCancelID.refresh, cancelInFlight: true)
```

`.send`はChild Featureの通信Effectを内包していない。Actionを受け取ったChild Featureが後から別のEffectを返すため、Parent Feature側のCancellation IDではその通信を管理できない。

## 通常のScopeで使う場合

[選択肢と判断基準](#選択肢と判断基準)で`trigger`を採用したChild Featureを通常の`Scope`で合成する場合、Parent Featureは次の形でActionを送る。

```swift
case let .view(viewAction):
  switch viewAction {
  case .onTappedReloadChildButton:
    return .send(.child(.trigger(.refresh)))
  }
```

この構成のキャンセル領域は[キャンセル領域の根拠](#キャンセル領域の根拠)、共通のCancellation IDによる処理の置き換えは[cancelInFlightを付ける場所](#cancelinflightを付ける場所)に従う。

## Effect.mapを新規設計で使わない

Discussion #1952では、Child FeatureのStateの`mutating`メソッドが`Effect<Child.Action>`を返し、Parent Featureが`.map { .child($0) }`する共有方法が示された。2023年時点のTCA 1では、Parent Featureから具体的なChild FeatureのActionを送らずに共有する実務的な方法だった。

一方、TCA 1.26.0の`Effect.map`には次の非推奨メッセージがある。

```text
Avoid transforming effects; construct them directly in a feature instead
```

通常構成では各OSへ`deprecated: 9999`が指定されるため警告は出ない。`ComposableArchitecture2Deprecations` traitを有効にすると実際の非推奨になる。TCA 1.25 Migration Guideの「Trait deprecations」は、TCA 2へ自分の予定で備えるための非推奨だと明記する。

したがって、`Effect.map`の非推奨理由はTCA 2への移行準備である。Parent FeatureからChild FeatureへActionを送る処理の性能が改善されたことを理由に方針が変わった、と説明しない。Action送信の性能は[性能と設計の判断](#性能と設計の判断)で扱う。

新規設計では[選択肢と判断基準](#選択肢と判断基準)に従って処理とEffectの所有者を決め、Child FeatureのEffectをParent FeatureのActionへ`map`する構造を標準にしない。

既存の`Effect.map`を機械的にすべて置き換えない。対象TCAの固定バージョン、Effectの所有者、キャンセル要件を確認して段階的に移行する。

## 性能と設計の判断

Parent FeatureからChild FeatureへActionを送ると、Store、Case Path、Feature合成を経由してChild Featureをもう一度処理する。直接ヘルパーを呼ぶより追加コストがある。

通信、データベース読み込み、明示的な再試行のような低頻度かつ意味のある処理では、通常、このAction送信コストより実処理のコストが大きい。ただし、これを性能保証として扱わない。計測が必要な箇所では計測する。

`trigger`を許容できる頻度と所有権の条件は[選択肢と判断基準](#選択肢と判断基準)で判断する。

## Featureのreduceを直接呼ばない

共有ロジックを再利用するために、Child FeatureをParent Featureから直接実行しない。

```swift
// 採用しない
return Child()
  .reduce(into: &state.child, action: .trigger(.refresh))
  .map { .child($0) }
```

TCA 1.25 Migration Guideでは、`reduce(into:action:)`の直接呼び出しが非推奨になった。ActionはStoreへ送るか、両Featureから呼べるヘルパーへ同期ロジックを抽出する。

代替となる処理の配置は[選択肢と判断基準](#選択肢と判断基準)で決める。`trigger`を採用した場合は[TCA 1のtrigger境界](#tca-1のtrigger境界)に従ってStoreへActionを送り、Feature合成、Dependency、Presentation、Cancellationの経路を保つ。

## Delegateとの関係

`delegate`は、Child Featureで起きた公開すべき結果をParent Featureへ伝える出力境界である。Parent Featureは`.child(.delegate(...))`を解釈できるが、Child Featureへ`.delegate(...)`を送らない。

Parent FeatureからChild Featureへの入力は[選択肢と判断基準](#選択肢と判断基準)と[TCA 1のtrigger境界](#tca-1のtrigger境界)で扱う。`delegate`を外部入力に使ったり、`trigger`をParent Featureへの通知に使ったりしない。

## TCA 2への移行

TCA 2開発版では、Parent FeatureからChild FeatureのActionを送る代わりに公式`Trigger`を使う。TCA 1のローカル`trigger`境界は、次の対応で機械的に見つけやすい。

| TCA 1 | TCA 2 |
| --- | --- |
| `case trigger(Trigger)` | 削除 |
| `Trigger.refresh` | Child FeatureのStateの`@Trigger var refresh` |
| Child Feature内部だけの共有Action | Featureローカルの`@Trigger private` |
| Featureローカル`refresh(state:)` | `.onTrigger(store.refresh)` |
| `.cancellable(id:cancelInFlight:)` | `@StoreTaskID`と`store.addTask(id:)` |
| Parent Featureの`.send(.child(.trigger(.refresh)))` | `store.addTask { try store.child.refresh() }` |
| Associated Valueを持つTrigger Case | `@Trigger<Value>` |

最小形は次のとおりである。

```swift
import ComposableArchitecture2

@Feature
struct Child {
  struct State {
    @Trigger var refresh
    @StoreTaskID var refreshTask
  }

  enum Action {
    case onAppear
  }

  var body: some Feature {
    Update { state, action in
      switch action {
      case .onAppear:
        store.addTask {
          try store.refresh()
        }
      }
    }
    .onTrigger(store.refresh) { state in
      store.addTask(id: state.refreshTask) {
        // Child Feature所有の非同期処理を行う
      }
    }
  }
}
```

Parent Featureは統合したChild FeatureのStoreのTriggerを非同期に呼ぶ。

```swift
case .onTappedReloadChildButton:
  store.addTask {
    try store.child.refresh()
  }
```

同じ`@StoreTaskID`を同じ`onTrigger`位置の`store.addTask(id:)`へ渡すと、次のTrigger呼び出しが前の実行中Taskを置き換えてキャンセルする。1回のUpdate内で同じIDを使って複数Taskを追加する場合は並列に追跡されるため、TCA 1の`cancelInFlight`と完全に同じだと一般化せず、固定したTCA 2リビジョンのテストを確認する。

TCA 2のPresentationや列挙型Storeのスコープ構文は開発中に変わり得る。移行時は固定リビジョンのTrigger資料、Lifecycle資料、テストを読み、TCA 1の構文を推測で移植しない。

## テスト観点

Actionの宣言順と`Reduce`の分岐方法は[Action Boundaries](action-boundaries.md)で検証する。この資料では、選択した所有者、入力方法、Effectの寿命を検証する。

- Parent Featureだけが行う同期State更新では、Parent FeatureのActionからChild FeatureのStateを直接更新する。
- Parent FeatureとChild Featureが同じ同期State更新を行う場合は、どちらのActionからも同じ`mutating`メソッドを使って同じStateへ遷移する。
- Parent Featureが所有するEffectの応答はParent Featureの`internal`へ戻り、Child FeatureへResponse Actionを送らない。
- Dependencyを共有する場合は、各Featureが自身のEffectを構築し、応答を自身の`internal`へ戻す。
- Child Featureの`view`からFeatureローカルヘルパーを呼ぶと、Child FeatureのStateが更新される。
- Parent FeatureのActionからChild Featureの`trigger`を受信し、同じヘルパーが開始される。
- 両方の開始経路で同じDependency結果をChild Featureの`internal`へ戻す。
- `cancelInFlight`により、後から開始した処理が同じChild Feature内の古い処理をキャンセルする。
- PresentationのChild Featureを破棄すると、Child FeatureのEffectがキャンセルされ、Response Actionが届かない。
- Parent Featureの`.send`へCancellation IDを付けていない。
- Trigger送信時にOptional、Presentation、Collection、Stack上の対象Child Featureが存在する。
- Child Featureが存在しない状態や、別Identityへ遅延送信しない。
- Parent FeatureはChild Featureの`view`、`internal`、`delegate`、`binding`を生成しない。
- 同期State更新の共有に`trigger`または`Effect.map`を使わない。
- TCA 2移行後はChild FeatureのActionの受信ではなく、Triggerによる観測可能なState変化を検証する。

Presentationを閉じた後もEffectを継続する要件の寿命モデルは、[Destinationパターン](destination-pattern.md)で検証する。

## 参照資料

- Parent FeatureからChild FeatureへActionを送る設計に関するTCA Discussion #1952: https://github.com/pointfreeco/swift-composable-architecture/discussions/1952
- TCA 1.26.0の`Effect.map`: https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.0/Sources/ComposableArchitecture/Effect.swift
- TCA 1.25 Migration GuideのTrait deprecations: https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.0/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.25.md#Trait-deprecations
- Parent FeatureからChild FeatureへActionを送る方法と性能上の注意: https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.0/Sources/ComposableArchitecture/Documentation.docc/Articles/Performance.md#Sharing-logic-in-child-features
- Presentation内のChild FeatureのEffectとParent FeatureのEffectの分離: https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.0/Sources/ComposableArchitecture/Reducer/Reducers/PresentationReducer.swift
- Cancellation IDと`navigationIDPath`: https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.0/Sources/ComposableArchitecture/Effects/Cancellation.swift
- Featureの`reduce`直接呼び出しの非推奨: https://github.com/pointfreeco/swift-composable-architecture/blob/1.26.0/Sources/ComposableArchitecture/Reducer.swift
- TCA 2開発版のTrigger: https://github.com/pointfreeco/TCA26/blob/main/Sources/ComposableArchitecture2/Documentation.docc/Articles/FeatureCommunication/FeatureCommunication-Triggers.md
- TCA 2開発版のParent FeatureとChild FeatureのTrigger実装例: https://github.com/pointfreeco/TCA26/blob/main/Examples/SwiftUICaseStudies/FeatureCommunication/Triggers.swift
- TCA 2開発版のStoreTaskID: https://github.com/pointfreeco/TCA26/blob/main/Sources/ComposableArchitecture2/StoreTaskID.swift
- TCA 2開発版のTask置換実装: https://github.com/pointfreeco/TCA26/blob/main/Sources/ComposableArchitecture2/FeatureDynamicProperties/FeatureStore.swift
- Discussion #1952を解説する日本語記事: https://zenn.dev/kalupas226/articles/87b1f7b245915c
