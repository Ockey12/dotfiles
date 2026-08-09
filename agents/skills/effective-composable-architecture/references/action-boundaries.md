# Action Boundaries

## 目次

- [位置づけ](#位置づけ)
- [分類手順](#分類手順)
- [最小構造](#最小構造)
- [Featureでの変換](#featureでの変換)
- [Viewから送るAction](#viewから送るaction)
- [Parent FeatureとChild Featureの境界](#parent-featureとchild-featureの境界)
- [Parent FeatureがChild FeatureのActionを使う条件](#parent-featureがchild-featureのactionを使う条件)
- [trigger境界](#trigger境界)
- [テスト観点](#テスト観点)
- [レビュー時の問題例](#レビュー時の問題例)
- [一次ソース](#一次ソース)

## 位置づけ

Action Boundariesは、Actionを発生元と通知先で分ける設計規約である。TCA 1が`trigger`、`internal`、`delegate`という名前を強制しているわけではない。

この資料の`trigger`はTCA 1専用のローカル規約である。TCA 2では同じ目的に公式`@Trigger`を使い、`trigger`のAction Caseを削除する。

## 分類手順

Action境界の分類とコード上の並びには、次の固定順序を使う。

1. ViewがBinding以外のユーザーの操作またはライフサイクルを伝える場合、`view`にする。
2. 別Featureが、このFeatureの所有する処理を起動する場合、`trigger`の候補にする。採用可否は[Parent FeatureがChild FeatureのActionを使う条件](#parent-featureがchild-featureのactionを使う条件)で判断する。
3. Effect、Dependency、タイマー、通知から戻る場合、`internal`にする。
4. Child FeatureがParent FeatureへActionを通知する場合、`delegate`にする。
5. `BindingAction<State>`の場合、`binding`にする。

Child Feature、Presentation、Navigation Stackを合成するActionは上記5境界に含めず、専用Caseとして5境界の後に置く。Action Case、ネストした境界Action型、資料内の一覧、`Reduce`内の`switch`では、存在する境界だけを抜き出して同じ順序を守る。この順序は可読性の規約であり、Featureの実行優先度を表さない。

`Reduce`では`view`、`trigger`、`internal`のAssociated Valueを外側の`switch`で取り出し、具体Caseを内側の`switch`で処理する。`case .trigger(.refresh)`のように、トップレベルActionと具体caseを同時にマッチさせない。

Action名は実装手段ではなく意味を表す。

| 境界 | 例 | 主な送信元 | 主な受信先 |
| --- | --- | --- | --- |
| `view` | `onTappedSaveButton` | View | 同じFeature |
| `trigger` | `refresh` | Parent Feature | Child Feature |
| `internal` | `getContentResponse` | Effect | 同じFeature |
| `delegate` | `onTappedCloseButton` | Child Feature | Parent Feature |
| `binding` | `BindingAction<State>` | ViewのBinding | `BindingReducer` |
| `child` | `ChildFeature.Action` | Child FeatureのStore、Parent Featureの`trigger`送信 | Child Feature |
| `destination` | `PresentationAction` | Presentation | Destination Feature |

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

`@Reducer`はトップレベルの`Action`へCase Path対応を生成する。ネストした`View`、`Trigger`、`Internal`、`Delegate`には`@CasePathable`を明示する。そうすることで、ネストしたActionをCasePathで記述できるようになる。

## Featureでの変換

Featureは境界を越える箇所を明示する。

Viewから始まる処理では、必要な境界だけを次の順序で変換する。

1. `view`を処理し、同期的なState更新またはEffectを開始する。
2. Effectを開始した場合、その値と失敗でStateを直接変更せず、`internal`としてFeatureへ戻す。
3. `internal`を処理し、Stateを更新する。
4. Parent Featureへ公開すべき結果がある場合、`delegate`を送る。Child Feature側で先に確定すべきStateがあれば、送信前に更新する。

Parent Feature起点の処理は[Parent FeatureがChild FeatureのActionを使う条件](#parent-featureがchild-featureのactionを使う条件)で所有者を決める。`trigger`を採用した場合の実装は[trigger境界](#trigger境界)に従う。

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

Viewから発生させるActionは`view`と`binding`に限定し、`trigger`、`internal`、`delegate`を直接送らない。

フォーム入力は`BindableAction`と`BindingReducer`を使い、通常は`$store`からBindingを作る。状態から導出できるBindingのために`Binding(get:set:)`を手書きしない。

`@ViewAction`の診断は境界違反を見つける補助である。マクロを付けただけで内部Actionがアクセス不能になるわけではない。
`ViewAction`は`Action`の中からView用Actionの型を特定する。`@ViewAction(for:)`はViewへ`send`を提供し、View内での直接的な`store.send`へ診断を出す。内部ActionをSwiftの型システムで完全に非公開にする仕組みではない。

## Parent FeatureとChild Featureの境界

Child FeatureはParent Featureへの通知を`delegate`として公開する。Parent Featureは`delegate`だけを解釈し、Child Featureの`view`、`trigger`、`internal`、`binding`に対する処理は実装しない。

```swift
// Parent Feature
case .child(.delegate(.didSave)):
  state.lastSavedAt = clock.now
  return .none
```

Child Featureは自身のDelegate Actionに対する処理を行わない。Delegate Actionの`.send`は、Parent Featureに通知するためだけに行う。

また、DelegateはInternalの処理の後にしか`.send`できない、というわけではない。Child Featureを`@Presents`でSheetとして表示する場合、閉じるボタンをタップした際の処理をParent Featureに委譲したい場合がある。処理の内容がEffectでの通信なら、完了する前にOptionalなChild FeatureのStateが破棄され、Effectもキャンセルされるため、Parent Featureが最後まで行う方が適している。そのような場合は、`Child.Action.View.onTappedCloseButton`から`Child.Action.Delegate.onTappedCloseButton`を`.send`する。

Presentation内のChild Featureから届くDelegateは次の形になる。

```swift
case .destination(.presented(.editor(.delegate(.didSave)))):
  state.destination = nil
  return .none
```

Parent Featureは、Child FeatureのDelegate Actionのうち、自身が処理したいcaseだけを`case .child(.delegate(.onTappedCloseButton))`のように取り出す。`case let .child(.delegate(delegateAction))`のように取り出して`switch delegateAction`で網羅する必要はない。こうすることで、Delegate Actionの各caseのシンボル検索を行った際に、実際に処理を行うFeatureを見つけやすくなったり、逆にどのFeatureからも使われていないcaseを見つけやすくなったりする。

## Parent FeatureがChild FeatureのActionを使う条件

Parent Featureは原則として、Child Featureへ処理を命令するためのAction Caseを構築しない。次の順序で責務を見直す。

1. Parent FeatureだけがChild FeatureのStateを同期更新するなら、Parent Featureで直接更新する。この更新だけを隠すParent Feature専用メソッドをChild FeatureのStateへ追加しない。
2. Parent Featureだけが所有する処理なら、Parent FeatureのState、Action、Dependencyへ置く。
3. Child Featureだけが所有し、外部からの起動が不要なら、Child Feature内から開始する。
4. Parent FeatureとChild Featureが同じ同期更新を行うなら、Child FeatureのStateの`mutating`メソッドを共有する。このメソッドはEffectを返さず、Parent Featureで`Effect.map`しない。
5. 複数Featureが別々にEffectを所有するなら、Dependencyの非同期APIを共有し、各FeatureでEffectを構築する。
6. Child Feature所有のEffectをParent Featureから起動する必要が残る場合だけ、TCA 1の`trigger`をParent Featureから送る。

`case child(ChildFeature.Action)`はFeature合成に必要である。禁止するのはcase自体ではなく、Parent FeatureがChild Featureの`view`、`internal`、`delegate`、`binding`を`.send`することである。完全な実装とキャンセル条件は[Parent FeatureからChild FeatureへActionを送らない](parent-child-communication.md)を読む。

## trigger境界

前節の責務見直しによって`trigger`を採用した場合、Actionのトップレベルに専用名前空間`Trigger`を置く。

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

`trigger`を`view`や`internal`と混ぜない。Child Featureの`view`と`trigger`で共通の処理があれば、両方から同じFeatureローカルヘルパー関数を直接呼ぶ。

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

## テスト観点

- View Actionが期待するStateだけを変更する。
- Effectの応答が`internal`として戻る。
- Child Featureの結果を理由にParent FeatureのStateを更新するのは、`delegate`受信時に限定する。
- Parent FeatureだけによるChild FeatureのState同期更新は直接行う。
- Parent FeatureとChild Featureが同じ同期更新を行う場合、Effectを返さない共有メソッドを使う。
- Parent Featureから送る具体的なChild FeatureのActionは`trigger`だけにする。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`を`view`、`trigger`、`internal`、`delegate`、`binding`の順に並べる。
- `view`、`trigger`、`internal`のAssociated Valueを取り出してから、内側の`switch`で具体Caseを処理する。
- Parent Featureの`trigger`とChild Featureの`view`が同じ処理を行うなら、Featureローカルヘルパーとして切り出す。
- Child Featureが、自身の`delegate`に対する処理を行わない。
- Child Featureの実処理に付けたCancellation IDが、どちらの開始元にも作用する。
- 一時的なChild Featureを破棄した後にResponse Actionが届かない。
- `binding`は`BindingReducer`で処理し、同じ変更をView Actionで重複実装しない。
- キャンセル時に完了ActionやDelegateを誤送信しない。

## レビュー時の問題例

- Viewが`.trigger(...)`、`.internal(...)`、`.delegate(...)`を直接`store.send()`している。
- API応答Actionが`view`または`trigger`に入っている。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`が`view`、`trigger`、`internal`、`delegate`、`binding`の順になっていない。
- `case .trigger(.refresh)`のように、トップレベルActionと具体Caseを同じパターンで処理している。
- Parent FeatureがChild Featureのボタン名、通信応答、Bindingを送信または解釈している。
- 高頻度の状態同期にParent FeatureからChild Featureへの`trigger`送信を使っている。
- Parent Featureだけの同期更新を、Parent Feature専用のChild FeatureのStateメソッドへ抽出している。
- Child FeatureのStateのメソッドがEffectを返し、Parent Featureで`Effect.map`している。
- Child Featureの`trigger`からParent Feature所有の処理を開始している。
- Parent Featureの`.send(.child(.trigger(...)))`へ`.cancellable`を付け、Child Featureの実処理には付けていない。
- Parent FeatureがChild Featureの`reduce(into:action:)`を直接呼んでいる。
- すべてのActionを`view`に入れ、Feature合成のActionまで隠している。
- `@ViewAction`を型レベルの完全なアクセス制御として説明している。

## 一次ソース

- TCAの`ViewAction`実装: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Observation/ViewAction.swift
- `@ViewAction`マクロの宣言: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Macros.swift
- View Action導入のMigration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.7.md
- Action分割に関するTCA Discussion: https://github.com/pointfreeco/swift-composable-architecture/discussions/1440
- Parent FeatureからChild FeatureへActionを送る方法と性能上の注意: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/Performance.md#Sharing-logic-in-child-features
- TCA 2開発版のTrigger: https://github.com/pointfreeco/TCA26/blob/main/Sources/ComposableArchitecture2/Documentation.docc/Articles/FeatureCommunication/FeatureCommunication-Triggers.md
