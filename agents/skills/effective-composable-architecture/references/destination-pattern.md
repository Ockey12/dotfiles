# Destinationパターン

## 目次

- [最初に寿命を決める](#最初に寿命を決める)
- [標準のPresentation](#標準のpresentation)
- [画面を閉じても存続するChild Feature](#画面を閉じても存続するchild-feature)
- [永続ChildのReducer](#永続childのreducer)
- [永続ChildのView](#永続childのview)
- [AlertStateとの組み合わせ](#alertstateとの組み合わせ)
- [キャンセル経路](#キャンセル経路)
- [Navigation Stackとの使い分け](#navigation-stackとの使い分け)
- [テスト観点](#テスト観点)
- [一次ソース](#一次ソース)

## 最初に寿命を決める

Destinationを表示方法だけで選ばない。Child StateとEffectをいつ破棄するかで選ぶ。

列挙型スコープはTCA 1.25.0で導入され、主要な修正が1.25.2に入った。この資料でAlertの明示Actionと空Caseを組み合わせる完全なパターンはTCA 1.25.5以降を前提とする。コード例はTCA 1.26.0以降のラベルなしScope APIを使う。TCA 1.25.5では同じ呼び出しに`state:`ラベルを付ける。

| 要件 | Child State | Destination Case | Dismiss時のChild Effect |
| --- | --- | --- | --- |
| 画面を閉じたら処理も終了する | DestinationのAssociated Value | `case child(ChildFeature)` | 自動キャンセル |
| 画面を閉じても処理を続ける | 親Stateの通常プロパティ | `case child` | Presentation由来ではキャンセルされない |
| 同型画面を複数積む | `StackState<Path.State>` | `Path`のAssociated Value | Pathから外れた要素のEffectを終了 |

## 標準のPresentation

表示とFeatureの寿命が一致する場合は、Child StateをDestinationへ入れる。

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
    case destination(PresentationAction<Destination.Action>)
    case view(View)

    @CasePathable
    enum View {
      case onTappedOpenChildButton
    }
  }

  var body: some ReducerOf<Self> {
    Reduce { state, action in
      switch action {
      case .view(.onTappedOpenChildButton):
        state.destination = .child(ChildFeature.State())
        return .none

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

`PresentationReducer`はPresentation Stateが`nil`になると、Child Reducerが開始した実行中のEffectを自動的にキャンセルする。画面を閉じても通信を続ける要件には、この形を使わない。

## 画面を閉じても存続するChild Feature

Child Featureの状態と処理をPresentationから分離する。

- Child Stateを親Stateの通常プロパティとして保持する。
- Child Actionを親Actionの通常Caseとして保持する。
- Child Reducerを通常の`Scope`で合成する。
- Destinationには表示中かどうかを表す空Caseだけを置く。
- DismissではDestinationだけを`nil`にし、Child Stateは残す。

この形は、ツールバーから進捗画面を開き、戻った後もアップロードやダウンロードを継続する場合などに使える。

## 永続ChildのReducer

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
    case child(ChildFeature.Action)
    case destination(PresentationAction<Destination.Action>)
    case view(View)

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
      case .view(.onTappedOpenChildButton):
        state.destination = .child
        return .none

      case .child, .destination:
        return .none
      }
    }
    .ifLet(\.$destination, action: \.destination)
  }
}
```

Child ActionはPresentation Actionの内側へ入れない。これにより、Child EffectはDestinationのキャンセル領域で起動せず、Destinationが`nil`になってもPresentation Reducerによる自動キャンセルの対象にならない。

Child Viewが保持するScoped Storeのインスタンス自体は、画面とともに解放される場合がある。継続を決めるのはStoreインスタンスの保持ではなく、親Storeに残るChild Stateと、通常の`Scope`で合成したReducerの寿命である。

## 永続ChildのView

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

このBindingは、元のOptionalが非`nil`なら`true`を返し、`false`の書き込みで元を`nil`にする。汎用的なOptionalから新しい値を作れないため、`true`の書き込みは実行時警告になる。表示開始は必ずView Actionを送り、Reducerで`state.destination = .child`を設定する。

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

Alertと永続Childの空Caseを同じDestinationへ入れる場合は、空CaseのActionを`Never`にする。

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

Alertを表示するReducerの最小形は次のとおり。

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

親Reducerは`.destination(.presented(.alert(.onTappedRetryButton)))`を処理する。Alertしか表示しないFeatureでは、単独の`@Presents var alert: AlertState<Action.Alert>?`の方が単純である。複数の表示を相互排他的に管理するときにDestinationへまとめる。

通信失敗と再試行EffectをChildが所有する場合は、Action経路を次のようにする。

```text
Child.internal.uploadFailed
→ Child.delegate.didFail
→ Parent.destination.alert
→ Destination.Alert.onTappedRetryButton
→ Child Stateのretry() → Effect<Child.Action> → map → Parent.child
```

親ReducerはAlert Actionを受け取り、Child Stateへ抽出した再試行メソッドを呼ぶ。具体的な子Actionを命令として送らず、Effectから生じるActionだけをReducer合成用の`child` Caseへ持ち上げる。

```swift
case .child(.delegate(.didFail)):
  state.destination = .alert(retryAlert)
  return .none

case .destination(.presented(.alert(.onTappedRetryButton))):
  return state.child.retry().map { .child($0) }
```

`retryAlert`は前述の`AlertState`である。`retry()`は同期的にChild Stateを更新し、Childが所有する`Effect<ChildFeature.Action>`を返す。Parent Reducerの処理がChild Stateの同期更新だけで完結し、Child Reducerから同じ更新を行わない場合は、このメソッドを追加せず、Parent Reducerで直接更新する。定義方法と設計理由は[親から子Actionを送らない](parent-child-communication.md)を読む。

## キャンセル経路

Child Stateを通常プロパティに移すだけで、すべてのキャンセルを無効化できるわけではない。

- `.ifLet(\.$destination, ...)`の自動キャンセルからは分離される。
- `.cancellable(id:)`に対する`.cancel(id:)`は引き続きEffectを止める。
- 親Store自体が破棄されればEffectも存続できない。
- `.task { await send(.start).finish() }`はViewのTaskとStoreTaskのキャンセルを連動させる。画面消失後も続ける処理を、この形のViewライフサイクルへ所有させない。

継続処理はボタンなどのAction、または画面より長く存続する親FeatureのActionから開始する。どのActionがキャンセルを所有するかをReducerに残す。

## Navigation Stackとの使い分け

単一の画面を表示中かどうかだけ管理するなら`@Presents`とDestinationを使う。複数の画面または同型Featureの複数インスタンスを積むなら`StackState<Path.State>`と`StackAction<Path.State, Path.Action>`を使う。

永続ChildをNavigation Stackへ表示する場合でも、Path要素へChild Stateを入れるとPop時に寿命が終了する。処理を残す要件では、Pathを表示経路として使い、長寿命の状態とEffectを親側の通常Stateへ置く。

## テスト観点

標準のPresentationでは次を確認する。

- Open ActionでDestinationにChild Stateが入る。
- Child Effectの実行中にDismissするとEffectがキャンセルされる。
- Dismiss後にChild Actionが親へ到達しない。

永続Childでは次を確認する。

- Open ActionでDestinationが`.child`になり、Child Stateは同一のままである。
- Child Effectの実行中に`.destination(.dismiss)`を送ってもChild Stateが残る。
- Dismiss後にDependencyの応答を進めると、Childの`internal` Actionを受信してStateが更新される。
- 再表示時に同じ進捗と結果を参照できる。
- 明示的なCancel ActionではEffectが終了する。
- 空CaseにはPresented Actionが存在せず、Open ActionとDismiss Actionだけで表示状態が変わる。

Alertとの組み合わせでは、Button Actionが`.destination(.presented(.alert(...)))`として届き、Alertの自動Dismiss後も永続Child Stateが変化しないことを確認する。

## 一次ソース

- TCA 1.25 Migration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.25.md
- 列挙型スコープを修正したTCA 1.25.2のコミット: https://github.com/pointfreeco/swift-composable-architecture/commit/658353cfea
- Alertの明示Actionを修正したTCA 1.25.5のコミット: https://github.com/pointfreeco/swift-composable-architecture/commit/b15c5bda01f820ee8c6231ce59f8cb7689339990
- ラベルなしScope APIを追加したTCA 1.26.0のコミット: https://github.com/pointfreeco/swift-composable-architecture/commit/de5e7aff89
- Presentation Reducerの自動キャンセル: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Reducer/Reducers/PresentationReducer.swift
- Reducerマクロの空Caseと`Never`の生成: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Tests/ComposableArchitectureMacrosTests/ReducerMacroTests.swift
- Swift NavigationのOptionalからBoolへのBinding: https://github.com/pointfreeco/swift-navigation/blob/main/Sources/SwiftNavigation/Binding.swift
