# Action Boundaries

## 目次

- [位置づけ](#位置づけ)
- [分類手順](#分類手順)
- [最小構造](#最小構造)
- [View Action](#view-action)
- [Trigger Action](#trigger-action)
- [Internal Action](#internal-action)
- [Delegate Action](#delegate-action)
- [テスト観点](#テスト観点)
- [レビュー時の問題例](#レビュー時の問題例)
- [一次ソース](#一次ソース)

## 位置づけ

Action Boundariesは、Actionを発生元と通知先で分ける設計規約である。TCA 1が`trigger`、`internal`、`delegate`という名前を強制しているわけではない。

この資料の`trigger`はTCA 1専用のローカル規約である。TCA 2では同じ目的に公式`@Trigger`を使い、`trigger`のAction Caseを削除する。

## 分類手順

Action境界の分類とコード上の並びには、次の固定順序を使う。

1. ViewがBinding以外のユーザーの操作またはライフサイクルを伝える場合、`view`にする。詳細は[View Action](#view-action)で判断する。
2. 別Featureが、このFeatureの所有する処理を起動する場合、`trigger`の候補にする。採用可否は[Child FeatureへActionを送りたい場合の選択肢と判断基準](parent-child-communication.md)で判断する。
3. Effect、Dependency、タイマー、通知から戻る場合、`internal`にする。詳細は[Internal Action](#internal-action)で判断する。
4. Child FeatureがParent FeatureへActionを通知する場合、`delegate`にする。詳細は[Delegate Action](#delegate-action)で判断する。
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

## View Action

`view`は、ViewがBinding以外のユーザー操作またはライフサイクルを同じFeatureへ伝える場合に使う。ボタンのタップ、タスクの開始、画面の表示など、Viewで発生した事実やユーザーの意図を表す。Effectの応答、別Featureからの開始要求、Parent Featureへの通知には使わない。

フォーム入力のような双方向更新は`view`ではなく`binding`にする。

具体的には、Featureの`Action`を`ViewAction`へ準拠させ、View用Actionをネストした`View`へ置く。Viewには`@ViewAction(for:)`を付け、生成される`send`でView用Actionを送る。

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
`ViewAction`は`Action`の中からView用Actionの型を特定する。`@ViewAction(for:)`はViewへ`send`を提供し、View内での直接的な`store.send`に警告を出す。内部ActionをSwiftの型システムで完全に非公開にする仕組みではない。

## Trigger Action

`trigger`は、別Featureが、このFeatureの所有するEffectを外部から起動する入力境界である。TCA 1専用のローカル規約であり、Parent FeatureからChild Featureへの一般的な命令APIではない。

Parent FeatureからChild FeatureへActionを送りたい場合は、先に[Child FeatureへActionを送りたい場合の選択肢と判断基準](parent-child-communication.md)を読む。Stateの同期更新、EffectとDependencyの所有者、起動元、頻度、Child FeatureのIdentityと寿命を比較し、Action送信が不要な構成を含む選択肢から選ぶ。`trigger`の採用条件、TCA 1での実装、Cancellation IDの置き場所、TCA 2への移行も同資料で扱う。

`trigger`を採用した場合は、Actionのトップレベルに専用の`Trigger`名前空間を置き、`view`や`internal`と混ぜない。Parent Featureが具体的なChild FeatureのActionとして送るのは`trigger`だけにする。`case child(ChildFeature.Action)`自体はFeature合成に必要だが、Child Featureの`view`、`internal`、`delegate`、`binding`をParent Featureから送らない。

Child Featureの`view`と`trigger`が同じ処理を開始する場合は、両方から同じFeatureローカルヘルパーを直接呼ぶ。Actionを相互に`.send`して中継しない。

## Internal Action

`internal`は、Effect、Dependency、タイマー、通知から値または失敗が戻り、同じFeatureがその結果を解釈する場合に使う。`view`または`trigger`の処理中に完結する同期State更新では、別の`internal`を送らず、その場でStateを更新する。

Effectの値または失敗をFeatureが扱う場合は、`internal`としてFeatureへ戻す。`internal`を処理する際にStateを更新し、Parent Featureへ公開すべき結果があれば、その後に`delegate`を送る。Child Feature側で確定すべきStateは、`delegate`の送信前に更新する。

[最小構造](#最小構造)では、`view`と`trigger`の両方が`save(state:)`を呼び、Effectが`.internal(.saveFinished)`を送る。Featureは`saveFinished`を受け取って`isSaving`を更新し、保存完了をParent Featureへ公開する必要があるため、最後に`.delegate(.didSave)`を送る。

ViewとParent FeatureはChild Featureの`internal`を送信または解釈しない。`internal`は同じFeature内の状態遷移に閉じる。

## Delegate Action

`delegate`は、Child Featureで起きた結果やユーザーの意図について、Parent Featureが自身のState、Navigation、またはEffectを判断する必要がある場合に使う。結果がChild Feature内だけで完結する場合は定義しない。Parent Featureへ公開する意味を名前にし、Child Feature内部の通信応答やState更新をそのまま公開しない。

Child FeatureはParent Featureへの通知を`delegate`として送る。Parent Featureは`delegate`だけを解釈し、Child Featureの`view`、`trigger`、`internal`、`binding`に対する処理は実装しない。

```swift
// Parent Feature
case .child(.delegate(.didSave)):
  state.lastSavedAt = clock.now
  return .none
```

Child Featureは自身のDelegate Actionに対する処理を行わない。Delegate Actionの`.send`は、Parent Featureに通知するためだけに行う。

Delegate ActionはInternal Actionの処理後にだけ送るものではない。Child Featureを`@Presents`でSheetとして表示し、閉じるボタンから始まる通信をDismiss後も継続する場合、Child FeatureのView ActionからDelegate Actionを送り、Parent Featureが通信を所有する。Child Featureが通信を開始すると、完了前にOptionalなStateが破棄され、Effectもキャンセルされるためである。

Presentation内のChild Featureから届くDelegate Actionは次の形になる。

```swift
case .destination(.presented(.editor(.delegate(.onTappedCloseButton)))):
  // Child Stateの値を使って通信や保存などを行う
  state.destination = nil
  return .none
```

Parent Featureは、Child FeatureのDelegate Actionのうち、自身が処理したいcaseだけを`case .child(.delegate(.onTappedCloseButton))`のように取り出す。`case let .child(.delegate(delegateAction))`のように取り出して`switch delegateAction`で網羅する必要はない。こうすることで、Delegate Actionの各caseのシンボル検索を行った際に、実際に処理を行うFeatureを見つけやすくなったり、逆にどのFeatureからも使われていないcaseを見つけやすくなったりする。

## テスト観点

- View Actionが期待するStateだけを変更する。
- Effectの応答が`internal`として戻る。
- Child Featureの結果を理由にParent FeatureのStateを更新するのは、`delegate`受信時に限定する。
- Parent Featureから送る具体的なChild FeatureのActionは`trigger`だけにする。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`を`view`、`trigger`、`internal`、`delegate`、`binding`の順に並べる。
- `view`、`trigger`、`internal`のAssociated Valueを取り出してから、内側の`switch`で具体Caseを処理する。
- Child Featureが、自身の`delegate`に対する処理を行わない。
- `binding`は`BindingReducer`で処理し、同じ変更をView Actionで重複実装しない。

## レビュー時の問題例

- Viewが`.trigger(...)`、`.internal(...)`、`.delegate(...)`を直接`store.send()`している。
- API応答Actionが`view`または`trigger`に入っている。
- Action Case、ネストした境界Action型、`Reduce`の外側の`switch`が`view`、`trigger`、`internal`、`delegate`、`binding`の順になっていない。
- `case .trigger(.refresh)`のように、トップレベルActionと具体Caseを同じパターンで処理している。
- Parent FeatureがChild Featureの`view`、通信応答、Bindingを送信したり対応する処理を実装したりしている。
- すべてのActionを`view`に入れ、Feature合成のActionまで隠している。
- `@ViewAction`を型レベルの完全なアクセス制御として説明している。

## 一次ソース

- TCAの`ViewAction`実装: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Observation/ViewAction.swift
- `@ViewAction`マクロの宣言: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Macros.swift
- View Action導入のMigration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.7.md
- Action分割に関するTCA Discussion: https://github.com/pointfreeco/swift-composable-architecture/discussions/1440
- Parent FeatureからChild FeatureへActionを送る方法と性能上の注意: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/Performance.md#Sharing-logic-in-child-features
- TCA 2開発版のTrigger: https://github.com/pointfreeco/TCA26/blob/main/Sources/ComposableArchitecture2/Documentation.docc/Articles/FeatureCommunication/FeatureCommunication-Triggers.md
