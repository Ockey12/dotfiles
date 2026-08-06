# Action Boundaries

## 目次

- [位置づけ](#位置づけ)
- [分類手順](#分類手順)
- [最小構造](#最小構造)
- [Reducerでの変換](#reducerでの変換)
- [Viewから送るAction](#viewから送るaction)
- [親子の境界](#親子の境界)
- [親が子Actionを使わない](#親が子actionを使わない)
- [テスト観点](#テスト観点)
- [レビュー時の問題例](#レビュー時の問題例)
- [一次ソース](#一次ソース)

## 位置づけ

Action Boundariesは、Actionを発生元と通知先で分ける設計規約である。TCAが`internal`、`delegate`という名前を強制しているわけではない。

`ViewAction`は`Action`の中からView用Actionの型を特定する。`@ViewAction(for:)`はViewへ`send`を提供し、View内での直接的な`store.send`へ診断を出す。内部ActionをSwiftの型システムで完全に非公開にする仕組みではない。

## 分類手順

Actionごとに次を順番に問う。

1. `BindingAction<State>`か。該当すれば`binding`にする。
2. Viewがユーザーの意図またはライフサイクルを伝えるか。該当すれば`view`にする。
3. Effect、Dependency、タイマー、通知から戻るか。該当すれば`internal`にする。
4. 子Reducer、Presentation、Navigation Stackを合成するためのActionか。該当する専用Caseにする。
5. 子Featureが親へ結果を通知するか。該当すれば`delegate`にする。

Action名は実装手段ではなく意味を表す。

| 境界 | 例 | 主な送信元 | 主な受信先 |
| --- | --- | --- | --- |
| `binding` | `BindingAction<State>` | ViewのBinding | `BindingReducer` |
| `view` | `onTappedSaveButton` | View | 同じFeature |
| `internal` | `saveFinished` | Effect | 同じFeature |
| `child` | `ChildFeature.Action` | 子Store | 子Reducer |
| `destination` | `PresentationAction` | Presentation | Destination Reducer |
| `delegate` | `didSave` | 子Feature | 親Feature |

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
    case binding(BindingAction<State>)
    case view(View)
    case `internal`(Internal)
    case delegate(Delegate)

    @CasePathable
    enum View {
      case onTappedSaveButton
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

  @Dependency(\.continuousClock) var clock

  var body: some ReducerOf<Self> {
    BindingReducer()
    Reduce { state, action in
      switch action {
      case .view(.onTappedSaveButton):
        state.isSaving = true
        return .run { send in
          try await clock.sleep(for: .seconds(1))
          await send(.internal(.saveFinished))
        }

      case .internal(.saveFinished):
        state.isSaving = false
        return .send(.delegate(.didSave))

      case .binding, .delegate:
        return .none
      }
    }
  }
}
```

`@Reducer`はトップレベルの`Action`へCase Path対応を生成する。ネストした`View`、`Internal`、`Delegate`をKey Path形式のテストやReducerで参照する場合は、各型へ`@CasePathable`を明示する。

## Reducerでの変換

Reducerは境界を越える箇所を明示する。

```text
View → view → Effect → internal → State更新 → delegate → Parent
Parentだけで完結し、Childと共有しないChild Stateの同期更新 → Parent Reducerで直接更新
ParentとChildが同じ同期更新を行う → Child Stateのメソッド
ParentからChildが所有するEffectを起動 → Child Stateのメソッド → Effect<Child.Action> → map → child → Child Reducer
```

- `view`ではユーザーの意図を解釈し、状態更新またはEffectを開始する。
- Effectの値と失敗は`internal`へ戻し、状態遷移をReducerに集約する。
- 親が知るべき結果だけを`delegate`として送る。
- `delegate`を送る前に、子が所有する状態を確定させる。
- Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新は、Parent Reducerで直接更新する。
- ParentとChildから同じ同期更新を行う場合は、Effectを返さないChild Stateのメソッドへ抽出する。
- ParentからChildが所有するEffectを起動する場合は、Effectを返すChild Stateのメソッドを使い、具体的な子Actionを送らない。

Effect内で親Stateを直接変更したり、Viewから`internal`を送ったりしない。

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

`@ViewAction`の診断は境界違反を見つける補助である。マクロを付けただけで内部Actionがアクセス不能になるとは説明しない。

## 親子の境界

親は子が公開した`delegate`を処理する。

```swift
case .child(.delegate(.didSave)):
  state.lastSavedAt = clock.now
  return .none
```

Parentが受け取った値でChild Stateを同期的に更新するだけで処理が完結し、Child Reducerから同じ更新を行わない場合は、Parent Reducerで直接更新する。この更新だけを隠す親専用メソッドをChild Stateへ追加しない。

```swift
case let .internal(.childProgressUpdated(progress)):
  state.child.progress = progress
  return .none
```

親のAlertからChildが所有する再試行Effectを起動する場合は、Child Stateへメソッドを定義する。親から子Actionを送らず、返されたEffectをReducer合成用のActionへ持ち上げる。

```swift
case .destination(.presented(.alert(.onTappedRetryButton))):
  return state.child.retry().map { .child($0) }
```

この例の`retry()`はChildが所有するEffectを返す。Parent Reducerの処理がChild Stateの同期更新だけで完結し、Child Reducerから同じ更新を行わない場合は、メソッドを追加せず、Parent Reducerで直接更新する。Child ReducerとParent Reducerが同じ同期的な更新を行う場合は、Effectを返さない共有メソッドへ抽出する。定義方法は[親から子Actionを送らない](parent-child-communication.md)を読む。

Presentation内の子であれば、形は次のようになる。

```swift
case .destination(.presented(.editor(.delegate(.didSave)))):
  state.destination = nil
  return .none
```

親が子の`view(.onTappedSaveButton)`や`internal(.saveFinished)`を処理すると、子の実装詳細が親のAPIになる。親へ伝える意味を`delegate`として命名する。

## 親が子Actionを使わない

親は、子へ処理を命令するためのAction Caseを追加しない。親Viewから`store.send(.child(...))`を呼んだり、親Reducerから`.send(.child(...))`を返したりしない。

親が子に関係する処理を所有する場合は、次の順序で責務を見直す。

1. Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新なら、Parent Reducerで直接更新する。
2. 親だけが所有するその他の処理なら、親のState、Action、Dependencyへ置く。
3. 子だけが所有する処理なら、子のViewまたはEffectから子Actionを送る。
4. 親と子の両方から必要なら、Child Stateへ共有メソッドを抽出する。
5. 子から親の判断が必要なら、意味のある`delegate`を送る。

`case child(ChildFeature.Action)`はReducer合成に必要である。禁止するのはこのCase自体ではなく、親が具体的な子Actionを命令として構築、解釈することである。

## テスト観点

- View Actionが期待するStateだけを変更する。
- Effectの応答が`internal`として戻る。
- `internal`の処理後に必要な`delegate`が送られる。
- 子の結果を理由に親Stateを更新するのは、`delegate`受信時に限定する。
- Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新は直接行い、親専用のChild Stateメソッドを追加していない。
- ParentとChildから同じ処理を起動するときはChild Stateの共有メソッドを使い、具体的な子Actionを送っていない。
- Effectを返す共有メソッドでは、そのActionが`child` Caseへmapされて子Reducerへ届く。
- `binding`は`BindingReducer`で処理され、同じ変更をView Actionで重複実装していない。
- キャンセル時に完了ActionやDelegateを誤送信しない。

## レビュー時の問題例

- Viewが`.internal(...)`または`.delegate(...)`を直接送っている。
- API応答Actionが`view`に入っている。
- 親が子のボタン名や通信応答を直接switchしている。
- 親Viewまたは親Reducerが子へ具体的なActionを送っている。
- Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新を、親専用のChild Stateメソッドへ抽出している。
- 親が子Reducerの`reduce(into:action:)`を直接呼んでいる。
- すべてのActionを`view`に入れ、Reducer合成のActionまで隠している。
- View ActionがUI部品の名前だけを表し、ユーザーの意図を表していない。
- `@ViewAction`を型レベルの完全なアクセス制御として説明している。

## 一次ソース

- TCAの`ViewAction`実装: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Observation/ViewAction.swift
- `@ViewAction`マクロの宣言: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Macros.swift
- View Action導入のMigration Guide: https://github.com/pointfreeco/swift-composable-architecture/blob/main/Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/MigratingTo1.7.md
- Action分割に関するTCA Discussion: https://github.com/pointfreeco/swift-composable-architecture/discussions/1440
