# Action Boundaries

## 目次

- [位置づけ](#位置づけ)
- [分類手順](#分類手順)
- [最小構造](#最小構造)
- [Reducerでの変換](#reducerでの変換)
- [Viewから送るAction](#viewから送るaction)
- [親子の境界](#親子の境界)
- [trigger境界](#trigger境界)
- [親が子Actionを使う条件](#親が子actionを使う条件)
- [テスト観点](#テスト観点)
- [レビュー時の問題例](#レビュー時の問題例)
- [一次ソース](#一次ソース)

## 位置づけ

Action Boundariesは、Actionを発生元と通知先で分ける設計規約である。TCA 1が`trigger`、`internal`、`delegate`という名前を強制しているわけではない。

`ViewAction`は`Action`の中からView用Actionの型を特定する。`@ViewAction(for:)`はViewへ`send`を提供し、View内での直接的な`store.send`へ診断を出す。内部ActionをSwiftの型システムで完全に非公開にする仕組みではない。

この資料の`trigger`はTCA 1専用のローカル規約である。TCA 2では同じ目的に公式`@Trigger`を使い、`trigger`のAction Caseを削除する。

## 分類手順

Action境界の分類とコード上の並びには、次の固定順序を使う。

1. ViewがBinding以外のユーザーの操作またはライフサイクルを伝える場合、`view`にする。
2. 別Featureが、このFeatureの所有する処理を起動する場合、設計見直し後も外部起動が必要なら`trigger`にする。
3. Effect、Dependency、タイマー、通知から戻る場合、`internal`にする。
4. 子Featureが親へActionを通知する場合、`delegate`にする。
5. `BindingAction<State>`の場合、`binding`にする。

子Reducer、Presentation、Navigation Stackを合成するActionは上記5境界に含めず、専用Caseとして5境界の後に置く。Action Case、ネストした境界Action型、資料内の一覧、`Reduce`内の`switch`では、存在する境界だけを抜き出して同じ順序を守る。この順序は可読性の規約であり、Reducerの実行優先度を表さない。

Action名は実装手段ではなく意味を表す。

| 境界 | 例 | 主な送信元 | 主な受信先 |
| --- | --- | --- | --- |
| `view` | `onTappedSaveButton` | View | 同じFeature |
| `trigger` | `refresh` | 親Feature | Child Reducer |
| `internal` | `getContentResponse` | Effect | 同じFeature |
| `delegate` | `onTappedCloseButton` | 子Feature | 親Feature |
| `binding` | `BindingAction<State>` | ViewのBinding | `BindingReducer` |
| `child` | `ChildFeature.Action` | 子Store、親の`trigger`送信 | 子Reducer |
| `destination` | `PresentationAction` | Presentation | Destination Reducer |

## 最小構造

```swift
import ComposableArchitecture

@Reducer
struct EditorFeature {
  @ObservableState
  struct State: Equatable {
    var isSaving = false
    var title = ""
  }

  enum Action: BindableAction, ViewAction {
    case view(View)
    case trigger(Trigger)
    case `internal`(Internal)
    case delegate(Delegate)
    case binding(BindingAction<State>)

    @CasePathable
    enum View {
      case onTappedSaveButton
    }

    @CasePathable
    enum Trigger {
      case save
    }

    @CasePathable
    enum Internal {
      case saveFinished
    }

    @CasePathable
    enum Delegate {
      case didSave
    }
  }

  @Dependency(\.continuousClock) private var clock

  var body: some ReducerOf<Self> {
    BindingReducer()
    Reduce { state, action in
      switch action {
      case let .view(viewAction):
        switch viewAction {
        case .onTappedSaveButton:
          return save(state: &state)
        }

      case let .trigger(triggerAction):
        switch triggerAction {
        case .save:
          return save(state: &state)
        }

      case let .internal(internalAction):
        switch internalAction {
        case .saveFinished:
          state.isSaving = false
          return .send(.delegate(.didSave))
        }

      case .delegate, .binding:
        return .none
      }
    }
  }

  private func save(state: inout State) -> Effect<Action> {
    state.isSaving = true
    return .run { send in
      try await clock.sleep(for: .seconds(1))
      await send(.internal(.saveFinished))
    }
  }
}
```

`@Reducer`はトップレベルの`Action`へCase Path対応を生成する。ネストした`View`、`Trigger`、`Internal`、`Delegate`をKey Path形式のテストやReducerで参照する場合、各型へ`@CasePathable`を明示する。

## Reducerでの変換

Reducerは境界を越える箇所を明示する。

```text
View → view → Childの処理 → internal → State更新 → delegate → Parent
Parent → Childのtrigger → Childの処理 → internal → State更新
ParentだけのChild State同期更新 → Parent Reducerで直接更新
ParentとChildが同じ同期更新を行う → Effectを返さないChild Stateメソッド
Parent所有の非同期処理 → Parent Effect → Parent internal
ParentとChildが個別に所有する同種の非同期処理 → 共有Dependency → 各FeatureのEffect
```

- `view`ではユーザーの意図を解釈し、状態更新またはEffectを開始する。
- `trigger`では外部Featureからの開始要求を解釈し、Child所有の処理を開始する。
- Effectの値と失敗は`internal`へ戻し、状態遷移をReducerに集約する。
- `Reduce`では各境界のAssociated Valueを取り出し、内側の`switch`で具体Caseを処理する。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`を`view`、`trigger`、`internal`、`delegate`、`binding`の順に並べる。
- 親が知るべき結果だけを`delegate`として送る。
- `delegate`を送る前に、子が所有する状態を確定させる。
- Parentだけの同期更新は、Parent ReducerからChild Stateを直接更新する。
- ParentとChildから同じ同期更新を行う場合、Effectを返さないChild Stateのメソッドへ抽出する。
- ParentとChildから同じChild所有Effectを開始する場合、両方の境界からReducerローカルヘルパーを直接呼ぶ。

Effect内で親Stateを直接変更したり、Viewから`trigger`、`internal`、`delegate`を送ったりしない。

## Viewから送るAction

```swift
import ComposableArchitecture
import SwiftUI

@ViewAction(for: EditorFeature.self)
struct EditorView: View {
  @Bindable var store: StoreOf<EditorFeature>

  var body: some View {
    Form {
      TextField("Title", text: $store.title)
      Button("Save") {
        send(.onTappedSaveButton)
      }
      .disabled(store.isSaving)
    }
  }
}
```

フォーム入力は`BindableAction`と`BindingReducer`を使い、通常は`$store`からBindingを作る。状態から導出できるBindingのために`Binding(get:set:)`を手書きしない。

`@ViewAction`の診断は境界違反を見つける補助である。マクロを付けただけで内部Actionがアクセス不能になるわけではない。

## 親子の境界

親は子が公開した`delegate`を処理する。親は子の`view`、`trigger`、`internal`、`binding`を受信できるが、それらに対する処理は実装しない。

```swift
// Parent
case .child(.delegate(.didSave)):
  state.lastSavedAt = clock.now
  return .none
```

Parentが受け取った値でChild Stateを同期的に更新するだけで処理が完結し、Child Reducerから同じ更新を行わない場合、Parent Reducerで直接更新する。この更新だけを隠す親専用メソッドをChild Stateへ追加しない。

```swift
// Parent
case let .internal(internalAction):
  switch internalAction {
  case let .getContentResponse(result):
    switch result {
    case let .success(response):
      state.child.content = response
      return .none

    case let .failure(error):
      // エラーハンドリング
      return .none
    }
  }
```

Child ReducerとParent ReducerがChild Stateの共通した同期更新を行う場合、Effectを返さないChild Stateの`mutating`メソッドへ抽出する。非同期処理を共有するために`Effect.map`を追加しない。これは、TCA 2移行を考慮してTCA 1で`Effect.map`が非推奨になったためである。

Child Featureは自身のDelegate Actionに対する処理を行わない。Delegate Actionの`.send`は、Parent Featureに通知するためだけに行う。

また、DelegateはInternalの処理の後にしか`.send`できない、というわけではない。Childを`@Presents`でSheetとして表示する場合、閉じるボタンをタップした際の処理をParent Featureに委譲したい場合がある。これは、処理の内容がEffectでの通信だった場合、完了する前にOptionalなChild Stateが破棄されてしまい、Effectもキャンセルされてしまうため、Parent Featureが最後まで行う方が適している。そのような場合は、`Child.Action.View.onTappedCloseButton`から`Child.Action.Delegate.onTappedCloseButton`を`.send`する。

Presentation内の子から届くDelegateは次の形になる。

```swift
case .destination(.presented(.editor(.delegate(.didSave)))):
  state.destination = nil
  return .none
```

親が子の`view(.onTappedSaveButton)`や`internal(.saveFinished)`を処理すると、子の実装詳細が親のAPIになる。親へ伝える意味を`delegate`として命名する。

親は、子のDelegate Actionのうち、自身が処理したいcaseだけを`case .child(.delegate(.onTappedCloseButton))`のように取り出す。`case let .child(.delegate(delegateAction))`のように取り出して`switch delegateAction`で網羅する必要はない。こうすることで、Delegate Actionの各caseのシンボル検索を行った際に、実際に処理を行うFeatureを見つけやすくなったり、逆にどのFeatureからも使われていないcaseを見つけやすくなったりする。

## trigger境界

TCA 1でChild所有の非同期処理をParentとChildの両方から起動する場合、Actionのトップレベルへ専用名前空間`Trigger`を置く。

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

`trigger`を`view`や`internal`へ混ぜない。Parentから送信してよいのは`trigger`だけである。各境界のActionを取り出してから再度`switch`し、Childの`view`と`trigger`で共通の処理があれば、同じReducerローカルヘルパー関数を直接呼ぶ。

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

一方からもう一方を`.send`すると、共有ロジックのためだけに余分なActionを処理し、テストにも中継Actionが現れるため避ける。また、`.send`は関数呼び出しよりも実行コストが高いため、ローカルヘルパー関数で実現できるなら`.send`は避ける。

## 親が子Actionを使う条件

親は原則として、子へ処理を命令するためのAction Caseを構築しない。次の順序で責務を見直す。

1. ParentだけがChild Stateの同期更新を行い、同様の更新をChildで行わないなら、Parent Reducerで直接更新する。
2. 親だけが所有する処理なら、親のState、Action、Dependencyへ置く。
3. 子だけが所有し、外部からの起動が不要なら、子の`view`または内部処理から開始する。
4. ParentとChildが同じ同期更新を行うなら、Child Stateの`mutating`メソッドを共有する。
5. 複数Featureが別々にEffectを所有するなら、Dependencyの非同期APIまたは純粋関数を共有する。
6. Child所有のEffectをParentから起動する必要が残る場合だけ、TCA 1の`trigger`をParentから送る。
7. 子から親の判断が必要なら、意味のある`delegate`を送る。

`case child(ChildFeature.Action)`はReducer合成に必要である。禁止するのはCase自体ではなく、親が子の`view`、`internal`、`delegate`、`binding`を`.send`することである。完全な実装とキャンセル条件は[親から子Actionを送らない](parent-child-communication.md)を読む。

## テスト観点

- View Actionが期待するStateだけを変更する。
- Effectの応答が`internal`として戻る。
- 子の結果を理由に親Stateを更新するのは、`delegate`受信時に限定する。
- ParentだけのChild State同期更新は直接行う。
- ParentとChildが同じ同期更新を行う場合、Effectを返さない共有メソッドを使う。
- Parentから送る具体的な子Actionは`trigger`だけにする。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`を`view`、`trigger`、`internal`、`delegate`、`binding`の順に並べる。
- `view`、`trigger`、`internal`のAssociated Valueを取り出してから、内側の`switch`で具体Caseを処理する。
- Parentの`trigger`とChildの`view`が同じReducerローカルヘルパーを起動する。
- Child Featureが、自身の`delegate`に対する処理を行わない。
- Childの実処理に付けたCancellation IDが、どちらの開始元にも作用する。
- 一時的なChildを破棄した後にResponse Actionが届かない。
- `binding`は`BindingReducer`で処理し、同じ変更をView Actionで重複実装しない。
- キャンセル時に完了ActionやDelegateを誤送信しない。

## レビュー時の問題例

- Viewが`.trigger(...)`、`.internal(...)`、`.delegate(...)`を直接`store.send()`している。
- API応答Actionが`view`または`trigger`に入っている。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`が`view`、`trigger`、`internal`、`delegate`、`binding`の順になっていない。
- `case .trigger(.refresh)`のように、トップレベルActionと具体Caseを同じパターンで処理している。
- 親が子のボタン名、通信応答、Bindingを送信または解釈している。
- 高頻度の状態同期にParentからChildへの`trigger`送信を使っている。
- Parentだけの同期更新を、親専用のChild Stateメソッドへ抽出している。
- Child StateのメソッドがEffectを返し、Parentで`Effect.map`している。
- Childの`trigger`からParent所有の処理を開始している。
- Parentの`.send(.child(.trigger(...)))`へ`.cancellable`を付け、Childの実処理には付けていない。
- 親が子Reducerの`reduce(into:action:)`を直接呼んでいる。
- すべてのActionを`view`に入れ、Reducer合成のActionまで隠している。
- `@ViewAction`を型レベルの完全なアクセス制御として説明している。

## 一次ソース

- TCAの`ViewAction`実装: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Observation/ViewAction.swift
- `@ViewAction`マクロの宣言: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Macros.swift
- View Action導入のMigration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.7.md
- Action分割に関するTCA Discussion: https://github.com/pointfreeco/swift-composable-architecture/discussions/1440
- ParentからChild Actionを送る方法と性能上の注意: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/Performance.md#Sharing-logic-in-child-features
- TCA 2開発版のTrigger: https://github.com/pointfreeco/TCA26/blob/main/Sources/ComposableArchitecture2/Documentation.docc/Articles/FeatureCommunication/FeatureCommunication-Triggers.md
