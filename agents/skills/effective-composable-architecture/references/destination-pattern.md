# Destinationパターン

## 目次

- [最初に寿命を決める](#最初に寿命を決める)
- [標準のPresentation](#標準のpresentation)
- [画面を閉じても存続するChild Feature](#画面を閉じても存続するchild-feature)
  - [Featureの実装](#featureの実装)
  - [Viewの実装](#viewの実装)
- [AlertStateとの組み合わせ](#alertstateとの組み合わせ)
- [キャンセル経路](#キャンセル経路)
- [Navigation Stackとの使い分け](#navigation-stackとの使い分け)
- [テスト観点](#テスト観点)
- [一次ソース](#一次ソース)

## 最初に寿命を決める

Destinationを表示方法だけで選ばない。Child FeatureのStateとEffectをいつ破棄するかで選ぶ。

列挙型スコープはTCA 1.25.0で導入され、主要な修正が1.25.2に入った。この資料でAlertの明示Actionと空Caseを組み合わせる完全なパターンはTCA 1.25.5以降を前提とする。コード例はTCA 1.26.0以降のラベルなしScope APIを使う。TCA 1.25.5では同じ呼び出しに`state:`ラベルを付ける。

| 要件 | 採用するパターン |
| --- | --- |
| 画面を閉じたら処理も終了する | [標準のPresentation](#標準のpresentation) |
| 画面を閉じても処理を続ける | [画面を閉じても存続するChild Feature](#画面を閉じても存続するchild-feature) |
| 同型画面を複数積む | [Navigation Stackとの使い分け](#navigation-stackとの使い分け) |

## 標準のPresentation

表示とFeatureの寿命が一致する場合は、Child FeatureのStateをDestinationへ入れる。

```swift
@Reducer
struct ParentFeature {
  @Reducer
  enum Destination {
    case child(ChildFeature)
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
      case onTappedOpenChildButton
    }
  }

  var body: some ReducerOf<Self> {
    Reduce { state, action in
      switch action {
      case let .view(viewAction):
        switch viewAction {
        case .onTappedOpenChildButton:
          state.destination = .child(ChildFeature.State())
          return .none
        }

      case .destination:
        return .none
      }
    }
    .ifLet(\.$destination, action: \.destination)
  }
}
```

TCA 1.26.0以降のViewでは、Destination全体へScopeしてからCaseを選ぶ。

```swift
.navigationDestination(
  item: $store.scope(\.$destination, action: \.destination).child
) { childStore in
  ChildView(store: childStore)
}
```

`PresentationReducer`はPresentation Stateが`nil`になると、Child Featureが開始した実行中のEffectを自動的にキャンセルする。画面を閉じても通信を続ける要件には、この形を使わない。

## 画面を閉じても存続するChild Feature

Child Featureの状態と処理をPresentationから分離する。

- Child FeatureのStateをParent FeatureのStateの通常プロパティとして保持する。
- Child FeatureのActionをParent FeatureのActionの通常Caseとして保持し、通常の`Scope`で合成する。Child FeatureのEffectはPresentation由来の自動キャンセルから分離される。
- Destinationには表示中かどうかを表す空Caseだけを置く。
- DismissではDestinationだけを`nil`にし、Child FeatureのStateは残す。

この形は、ツールバーから進捗画面を開き、戻った後もアップロードやダウンロードを継続する場合などに使える。

### Featureの実装

```swift
@Reducer
struct ParentFeature {
  @Reducer
  enum Destination {
    case child
  }

  @ObservableState
  struct State {
    var child = ChildFeature.State()
    @Presents var destination: Destination.State?
  }

  enum Action: ViewAction {
    case view(View)
    case child(ChildFeature.Action)
    case destination(PresentationAction<Destination.Action>)

    @CasePathable
    enum View {
      case onTappedOpenChildButton
    }
  }

  var body: some ReducerOf<Self> {
    Scope(\.child, action: \.child) {
      ChildFeature()
    }

    Reduce { state, action in
      switch action {
      case let .view(viewAction):
        switch viewAction {
        case .onTappedOpenChildButton:
          state.destination = .child
          return .none
        }

      case .child, .destination:
        return .none
      }
    }
    .ifLet(\.$destination, action: \.destination)
  }
}
```

Child FeatureのViewが保持するScoped Storeのインスタンス自体は、画面とともに解放される場合がある。継続を決めるのはStoreインスタンスの保持ではなく、Parent FeatureのStoreに残るChild FeatureのStateと、通常の`Scope`で合成したChild Featureの寿命である。

### Viewの実装

空のDestination CaseをScopeすると`Binding<Void?>`になる。Swift Navigationが提供する`Binding.init(_:)`で`Binding<Bool>`へ変換する。

```swift
@ViewAction(for: ParentFeature.self)
struct ParentView: View {
  @Bindable var store: StoreOf<ParentFeature>

  var body: some View {
    Form {
      Button("Open progress") {
        send(.onTappedOpenChildButton)
      }
    }
    .navigationDestination(
      isPresented: Binding(
        $store.scope(\.$destination, action: \.destination).child
      )
    ) {
      ChildView(
        store: store.scope(\.child, action: \.child)
      )
    }
  }
}
```

このBindingは、元のOptionalが非`nil`なら`true`を返し、`false`の書き込みで元を`nil`にする。汎用的なOptionalから新しい値を作れないため、`true`の書き込みは実行時警告になる。表示開始は必ずView Actionを送り、Featureで`state.destination = .child`を設定する。

## AlertStateとの組み合わせ

TCA 1.25.5以降で、Alert Actionを持つ`AlertState`とFeature Caseを同じ`@Reducer enum Destination`へ入れる場合は、非Feature Caseを明示する。

```swift
@Reducer
enum Destination {
  @ReducerCaseIgnored
  case alert(AlertState<Alert>)
  case child(ChildFeature)

  @CasePathable
  enum Action {
    case alert(Alert)
    case child(ChildFeature.Action)
  }

  enum Alert {
    case onTappedRetryButton
  }
}
```

Alertと永続するChild Featureの空Caseを同じDestinationへ入れる場合は、空CaseのActionを`Never`にする。

```swift
@Reducer
enum Destination {
  @ReducerCaseIgnored
  case alert(AlertState<Alert>)
  case child

  @CasePathable
  enum Action {
    case alert(Alert)
    case child(Never)
  }

  enum Alert {
    case onTappedRetryButton
  }
}
```

Alertを表示するFeatureの最小形は次のとおり。

```swift
state.destination = .alert(
  AlertState {
    TextState("Upload failed")
  } actions: {
    ButtonState(action: .onTappedRetryButton) {
      TextState("Retry")
    }
  }
)
```

ViewではDestination全体へScopeしてからAlert Caseを渡す。

```swift
.alert(
  $store.scope(\.$destination, action: \.destination).alert
)
```

Parent Featureは`.destination(.presented(.alert(.onTappedRetryButton)))`を処理する。Alertしか表示しないFeatureでは、単独の`@Presents var alert: AlertState<Action.Alert>?`の方が単純である。複数の表示を相互排他的に管理するときにDestinationへまとめる。

通信失敗と再試行のドメインロジックを永続するChild Featureが所有し、Parent FeatureのAlertから再試行を起動する場合、Actionの処理順序は次のとおりである。

1. Child Featureが`internal.uploadFailed`を受け取る。
2. Child Featureが`delegate.didFail`を送る。
3. Parent Featureが`destination.alert`を設定する。
4. `Destination.Alert.onTappedRetryButton`を受け取る。
5. Parent Featureが`Effect.send`を実行する。
6. Child Featureが`trigger.retry`を受け取る。
7. Child Featureが再試行Effectを開始する。

手順2から7の実装例は次のとおりである。

```swift
case .child(.delegate(.didFail)):
  state.destination = .alert(retryAlert)
  return .none

case .destination(.presented(.alert(.onTappedRetryButton))):
  return .send(.child(.trigger(.retry)))
```

`retryAlert`は前述の`AlertState`である。この例のChild Featureは永続するため、`trigger`はDismiss時の自動キャンセルではなく、Child Feature自身とParent FeatureからChild Feature所有の再試行を起動する境界として使う。`trigger`の採用条件、実装方法、Cancellation IDの置き場所、別の所有者を選ぶ条件、TCA 2への移行は[Child FeatureへActionを送りたい場合の選択肢と判断基準](parent-child-communication.md)を読む。

## キャンセル経路

Child FeatureのStateを通常プロパティに移すだけで、すべてのキャンセルを無効化できるわけではない。

- `.ifLet(\.$destination, ...)`の自動キャンセルからは分離される。
- `.cancellable(id:)`に対する`.cancel(id:)`は引き続きEffectを止める。
- Parent FeatureのStore自体が破棄されればEffectも存続できない。
- `.task { await send(.start).finish() }`はViewのTaskとStoreTaskのキャンセルを連動させる。画面消失後も続ける処理を、この形のViewライフサイクルへ所有させない。

継続処理はボタンなどのAction、または画面より長く存続するParent FeatureのActionから開始する。どのActionがキャンセルを所有するかをFeatureに残す。

## Navigation Stackとの使い分け

単一の画面を表示中かどうかだけ管理するなら`@Presents`とDestinationを使う。複数の画面または同型Featureの複数インスタンスを積むなら`StackState<Path.State>`と`StackAction<Path.State, Path.Action>`を使う。

永続するChild FeatureをNavigation Stackへ表示する場合でも、Path要素へChild FeatureのStateを入れるとPop時に寿命が終了する。処理を残す要件では、Pathを表示経路として使い、長寿命の状態とEffectをParent Feature側の通常Stateへ置く。

## テスト観点

標準のPresentationでは次を確認する。

- Open ActionでDestinationにChild FeatureのStateが入る。
- Child FeatureのEffectの実行中にDismissするとEffectがキャンセルされる。
- Dismiss後にChild FeatureのActionがParent Featureへ到達しない。

永続するChild Featureでは次を確認する。

- Open ActionでDestinationが`.child`になり、Child FeatureのStateは同一のままである。
- Child FeatureのEffectの実行中に`.destination(.dismiss)`を送ってもChild FeatureのStateが残る。
- Dismiss後にDependencyの応答を進めると、Child Featureの`internal` Actionを受信してStateが更新される。
- 再表示時に同じ進捗と結果を参照できる。
- 明示的なCancel ActionではEffectが終了する。
- 空CaseにはPresented Actionが存在せず、Open ActionとDismiss Actionだけで表示状態が変わる。

Alertとの組み合わせでは、Button Actionが`.destination(.presented(.alert(...)))`として届き、Alertの自動Dismiss後も永続するChild FeatureのStateが変化しないことを確認する。

## 一次ソース

- TCA 1.25 Migration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.25.md
- 列挙型スコープを修正したTCA 1.25.2のコミット: https://github.com/pointfreeco/swift-composable-architecture/commit/658353cfea
- Alertの明示Actionを修正したTCA 1.25.5のコミット: https://github.com/pointfreeco/swift-composable-architecture/commit/b15c5bda01f820ee8c6231ce59f8cb7689339990
- ラベルなしScope APIを追加したTCA 1.26.0のコミット: https://github.com/pointfreeco/swift-composable-architecture/commit/de5e7aff89
- `PresentationReducer`の自動キャンセル: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Reducer/Reducers/PresentationReducer.swift
- `@Reducer`マクロの空Caseと`Never`の生成: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Tests/ComposableArchitectureMacrosTests/ReducerMacroTests.swift
- Swift NavigationのOptionalからBoolへのBinding: https://github.com/pointfreeco/swift-navigation/blob/main/Sources/SwiftNavigation/Binding.swift
