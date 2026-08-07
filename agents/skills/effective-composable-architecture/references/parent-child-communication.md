# 親から子Actionを送らない

## 目次

- [原則](#原則)
- [送信を避ける理由](#送信を避ける理由)
- [選択基準](#選択基準)
- [ParentだけがChild Stateを更新する](#parentだけがchild-stateを更新する)
- [同期処理を共有する](#同期処理を共有する)
- [Effectを伴う処理を共有する](#effectを伴う処理を共有する)
- [Child破棄に連動するEffectの例外](#child破棄に連動するeffectの例外)
- [mapの役割](#mapの役割)
- [直接Reducerを呼ばない](#直接reducerを呼ばない)
- [Delegateとの関係](#delegateとの関係)
- [テスト観点](#テスト観点)
- [参照資料](#参照資料)

## 原則

親Viewまたは親Reducerから、処理の命令として具体的な子Actionを原則として送らない。

```swift
// 採用しない
return .send(.child(.refresh))
```

Parent Reducerの処理がChild Stateの同期更新だけで完結し、その更新をChild Reducerから行わない場合は、Parent Reducerで直接更新する。Child Stateへ親専用のメソッドを追加しない。

親と子の両方から同じ処理を起動する必要がある場合は、基本的にその処理をChild Stateの`mutating`メソッドへ抽出する。同期的な状態更新はメソッド内で行い、後続のActionを発生させるEffectがあれば`Effect<ChildFeature.Action>`として返す。

親は返されたEffectを`.map { .child($0) }`で親Actionへ持ち上げる。親が知るのは共有メソッドとReducer合成用の`child` Caseだけであり、具体的な子Action Caseではない。

例外として、一時的なChildが所有するEffectをChild破棄時に自動キャンセルする必要がある場合は、設計を再検討した上で、Parentから専用のTrigger Actionを送ってよい。ParentからChild Stateのメソッドを呼んで返したEffectはParent側のEffectとなり、Child破棄時の自動キャンセル領域には入らないためである。この例外は親子間の命令を一般化するものではない。

## 送信を避ける理由

TCAのActionは、Viewでの操作、Dependencyからの応答、子から親への通知など、システム内で起きた出来事を表す。Reducerのメソッド名や、別Featureから実行する命令として扱わない。

親が`.child(.refresh)`を作る設計には次の問題がある。

- 子Actionの具体的なCaseが親のAPIになる。
- 子の処理手順を変えるだけで、親Reducerと親のテストも変更しやすくなる。
- View由来でもEffect由来でもないActionが、親から子への命令として追加される。
- 子のAction境界を分けても、親がその内部Caseへ依存すれば境界が崩れる。

Discussion #1952でTCAのメンテナは、親が子Actionを送る2つの形をどちらも推奨せず、Child Stateのメソッドへ処理を抽出し、そのEffectを親Actionへmapする形を示している。

## 選択基準

| 要件 | 置き場所 |
| --- | --- |
| Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新 | Parent ReducerからChild Stateを直接更新 |
| 親だけが所有するその他の処理 | 親のState、Action、Dependency |
| 子だけが所有する処理 | 子のView ActionまたはEffect応答 |
| Child ReducerとParent Reducerが同じ更新または処理を行う | Child Stateの共有メソッド |
| ParentからEffectを起動し、Parent側の寿命または明示的なキャンセルで管理する処理 | Effectを返すChild Stateのメソッド |
| 一時的なChildが所有し、Child破棄時に自動キャンセルするEffect | 設計を再検討した後、ParentからChildの専用Trigger Actionを送る例外 |
| 子から親の判断を求める通知 | 子の`delegate` |

共有メソッドへ抽出しても責務が不自然なら、処理の所有者が子ではない可能性がある。複数Featureにまたがる処理は、共通の親FeatureまたはDependencyへ引き上げる。

## ParentだけがChild Stateを更新する

Parentが受け取ったEffectの応答や観測値によってChild Stateを同期的に更新するだけで処理が完結し、Child Reducerから同じ更新を行わない場合は、Parent Reducerで直接更新する。

```swift
case let .internal(.childProgressUpdated(progress)):
  state.child.progress = progress
  return .none
```

この代入だけを隠す`updateProgressFromParent(_:)`のようなメソッドをChild Stateへ追加しない。ChildがParentのActionやデータ取得手順を意識するAPIになり、状態更新の所有者が不明確になるためである。

## 同期処理を共有する

Child ReducerとParent Reducerが同じ同期的な状態更新を行う場合は、Child Stateのメソッドへ抽出する。同期的な状態更新だけなら、Effectを返さない。

```swift
extension ChildFeature.State {
  mutating func clearSelection() {
    selectedID = nil
  }
}
```

子Reducerと親Reducerのどちらからも同じメソッドを呼べる。

```swift
case .view(.onTappedClearButton):
  state.clearSelection()
  return .none
```

```swift
case .view(.onTappedClearChildSelectionButton):
  state.child.clearSelection()
  return .none
```

常に`.none`しか返さないメソッドを`Effect`型にしない。状態不変条件をメソッドへ集約し、呼び出し元に同じ更新を重複させない。

## Effectを伴う処理を共有する

次の例では、更新処理をChild Stateの`refresh()`へ抽出する。子ReducerはView Actionから呼び、親Reducerは親自身のView Actionから同じ処理を呼ぶ。

```swift
import ComposableArchitecture

@Reducer
struct ChildFeature {
  @ObservableState
  struct State: Equatable {
    var isRefreshing = false

    mutating func refresh() -> Effect<ChildFeature.Action> {
      @Dependency(\.continuousClock) var clock

      isRefreshing = true
      return .run { send in
        try await clock.sleep(for: .seconds(1))
        await send(.internal(.refreshFinished))
      }
    }
  }

  enum Action: ViewAction {
    case view(View)
    case `internal`(Internal)

    @CasePathable
    enum View {
      case onTappedRefreshButton
    }

    enum Internal {
      case refreshFinished
    }
  }

  var body: some ReducerOf<Self> {
    Reduce { state, action in
      switch action {
      case .view(.onTappedRefreshButton):
        return state.refresh()

      case .internal(.refreshFinished):
        state.isRefreshing = false
        return .none
      }
    }
  }
}
```

親は具体的な`ChildFeature.Action`を生成しない。共有メソッドが返すEffectの出力だけを、Reducer合成用のCaseへ変換する。

```swift
@Reducer
struct ParentFeature {
  @ObservableState
  struct State: Equatable {
    var child = ChildFeature.State()
  }

  enum Action: ViewAction {
    case child(ChildFeature.Action)
    case view(View)

    @CasePathable
    enum View {
      case onTappedRefreshChildButton
    }
  }

  var body: some ReducerOf<Self> {
    Scope(\.child, action: \.child) {
      ChildFeature()
    }

    Reduce { state, action in
      switch action {
      case .view(.onTappedRefreshChildButton):
        return state.child.refresh().map { .child($0) }

      case .child:
        return .none
      }
    }
  }
}
```

サンプルの待機処理はDependencyを使う最小例である。実際の通信ではAPI ClientなどのDependencyを使い、成功と失敗を子の`internal` Actionへ戻す。

このサンプルのChildは通常の`Scope`で常に存在する。Parentから`state.child.refresh()`を呼んでも、Childだけが破棄される境界はない。Optional、Presentation、`forEach`、Stack上の一時的なChildでは、次の例外を確認する。

## Child破棄に連動するEffectの例外

Parent ReducerからChild Stateのメソッドを呼ぶと、メソッドが`Child.State`に定義されていても、返されたEffectはParent ReducerのEffectになる。

```swift
case .view(.onTappedRefreshChildButton):
  guard state.child != nil else { return .none }
  return state.child!.refresh().map { .child(.presented($0)) }
```

PresentationReducerから見ると、このEffectはChild Reducerが返す`destinationEffects`ではなく、Parent Reducerが返す`baseEffects`である。`.map`は出力Actionの型を変換するだけであり、EffectをChildのライフサイクルへ移さない。そのため、Childが`nil`になっても、TCAによるChild破棄時の自動キャンセルは働かない。

この実装を必要とした時点で、次を順に再検討する。

1. 通信や監視は本当にChildが所有し、画面を閉じたら停止してよいか。
2. Parentまたは永続FeatureがEffectと結果を所有し、Childは状態を表示するだけにできないか。
3. Child StateをParentの通常プロパティとして保持し、Destinationには表示マーカーだけを置くべきではないか。
4. Parent側でChildのIdentityを含むCancellation IDを使い、破棄時の`.cancel(id:)`とResponse受信時のIdentity照合を明示する方が自然ではないか。
5. ParentからChildを命令したくなること自体が、親子境界、Feature分割、または共有データの所有者の誤りを示していないか。

再検討後も、次の条件をすべて満たす場合だけ例外を使う。

- Effectは一時的なChildが所有する。
- Childが破棄されたらEffectも停止する。
- ParentとChildの両方から同じ開始処理が必要である。
- Parent所有、永続Child、または明示的なキャンセルより、Childの自動キャンセル領域へ入れる方が責務を正しく表す。

TCA 1では、Parentから専用のTrigger Actionを即座に送信し、Child ReducerからEffectを返す。

```swift
// Parent Reducer
case .view(.onTappedRefreshChildButton):
  guard state.child != nil else { return .none }
  return .send(.child(.presented(.refreshRequested)))

// Child Reducer
case .refreshRequested:
  return state.refresh()
```

`.send`自体はParent Reducerが返すEffectである。送られたActionがStoreへ入り直し、PresentationReducer、`ifLet`、`forEach`、またはStack Reducerを経由してChild Reducerが返したEffectに、Child固有のキャンセル領域が付く。Childを破棄すると、このEffectが自動キャンセルされる。

専用のTrigger Actionは、`refreshRequested`のように例外だと分かるトップレベルのCaseとし、子の`view`や`internal`を偽装しない。非公式の`Input`名前空間を追加する必要はない。Parentが通信を開始し、完了後にChildのResponse Actionだけを送っても、通信はParent側のEffectのままであり、この例外の目的を満たさない。

送信時にChildが存在することを確認する。同じParent ActionでChildを破棄せず、遅延後にTrigger Actionを送らない。Childが存在しない状態でActionが届くと、TCAはロジック上の問題として報告する。

## mapの役割

`state.child.refresh()`の戻り値は`Effect<ChildFeature.Action>`であり、親Reducerは`Effect<ParentFeature.Action>`を返す必要がある。`.map { .child($0) }`は、Effectが将来出力する子Actionを親Actionの`child` Caseで包む。

```text
Child Stateの同期更新
→ Effect<Child.Action>
→ map
→ Effect<Parent.Action.child>
→ Scope
→ Child Reducer
```

これは`.send(.child(.refresh))`とは異なる。親は処理開始用の子Actionを構築せず、共有メソッドが生成したEffectの出力型を合成境界へ変換しているだけである。

ただし、`.map`はEffectのキャンセル領域をChildへ移さない。一時的なChildの破棄時にEffectを自動キャンセルする要件では、明示的なCancellation IDを使うか、前節の専用Trigger Actionの例外を判断する。

Discussion #1952の例は`.map(Action.child)`を使う。Swift 6のStrict Concurrencyではenum caseを関数参照として渡すとSendable警告が発生し得るため、この資料ではTCA 1.15 Migration Guideに従って`.map { .child($0) }`を使う。

## 直接Reducerを呼ばない

共有ロジックを再利用するために、子Reducerを親から直接実行しない。

```swift
// 採用しない
return ChildFeature()
  .reduce(into: &state.child, action: .view(.onTappedRefreshButton))
  .map { .child($0) }
```

TCA 1.25 Migration Guideでは、`reduce(into:action:)`の直接呼び出しが非推奨になった。現行の`Reducer.swift`にある非推奨メッセージも、新しいActionをStoreへ送らない場合は、両Reducerから呼べるヘルパーを抽出するよう案内している。

同じメッセージは`.send(.child(...))`も機械的な移行手段として示す。しかし、親子で処理を共有する設計では親が具体的な子Actionへ依存するため、このスキルではChild Stateの共有メソッドを優先する。

## Delegateとの関係

共有メソッドは親から子のロジックを起動する境界であり、`delegate`は子から親へ結果や判断材料を通知する境界である。役割を入れ替えない。

```text
Parent Action → Child Stateの共有メソッド
Childで起きた公開すべき結果 → Child.delegate → Parent Reducer
```

親は`.child(.delegate(...))`だけを解釈する。子の`view`や`internal`を親がswitchしない。

## テスト観点

- Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新では、Parent ActionからChild Stateを直接更新する。
- Parent専用の代入を隠すためだけのChild Stateメソッドを追加していない。
- 子のView Actionから共有メソッドを呼ぶと、同期Stateが更新される。
- 親のActionから同じ共有メソッドを呼ぶと、同じ同期Stateが更新される。
- 共有メソッドが返したEffectのActionは、親の`child` Caseを経て子Reducerへ届く。
- 親Reducerは具体的な子の`view`または`internal` Actionを生成、解釈しない。
- Effect完了後に子Stateが期待どおり更新される。
- キャンセル要件がある場合は、共有メソッドが返すEffectへ明示的なCancellation IDを付け、所有者から停止できる。
- 専用Trigger Actionの例外では、Parent ActionからChild ReducerがEffectを開始し、Child破棄時に自動キャンセルされる。
- 専用Trigger Actionを送った後にChildを破棄しても、存在しないChildへのResponse Actionが届かない。

Presentationを閉じた後もEffectを継続する要件では、共有メソッドだけでなくChild StateとReducerの寿命も確認する。[Destinationパターン](destination-pattern.md)に従い、Child Stateを親の通常プロパティとして保持する。

## 参照資料

- 親から子Actionを送る設計に関するTCA Discussion #1952: https://github.com/pointfreeco/swift-composable-architecture/discussions/1952
- Reducer直接呼び出しの非推奨メッセージ: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Reducer.swift
- TCA 1.25 Migration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.25.md
- enum caseの関数参照に関するTCA 1.15 Migration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.15.md
- ParentからChild Actionを送る方法と性能上の注意: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/Performance.md#Sharing-logic-in-child-features
- Presentation内のChild EffectとParent Effectの分離: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Reducer/Reducers/PresentationReducer.swift
- Discussion #1952を解説する日本語記事: https://zenn.dev/kalupas226/articles/87b1f7b245915c
