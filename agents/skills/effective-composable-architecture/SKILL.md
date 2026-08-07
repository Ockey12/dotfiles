---
name: effective-composable-architecture
description: The Composable Architecture（TCA）のFeatureを設計、実装、レビュー、リファクタリングするときに使う。Action Boundaries（view、internal、delegate、binding、子Action）、ViewAction、親から子Actionを送らないロジック共有とChild破棄時の自動キャンセルに限る例外、EffectとDependency、Destination、AlertState、Sheet、NavigationStack、画面を閉じた後も処理を継続するChild Featureのライフサイクル設計を扱う。
---

# Effective Composable Architecture

## 目的

Featureの入力境界、状態の所有権、Effectの寿命をコードから説明できる設計にする。特定のアプリ固有の名前や前提を例へ持ち込まない。

## 成果条件

- View、Effect、子Feature、親Featureから届くActionを分類できる。
- 親が具体的な子Actionを命令として送らない原則と、Child破棄時の自動キャンセルに限る例外を区別できる。
- 画面の表示期間とChild Featureの寿命が一致するかを判断できる。
- 対象プロジェクトが固定するTCAのAPIで実装できる。
- 境界とライフサイクルをTestStoreで検証できる。
- 変更理由と一次ソースを報告できる。

## 一次ソースの確認

`pfw-composable-architecture`スキルを使用できる場合、まずはそのスキルを参照する。この`effective-composable-architecture`スキルは、TCAをさらに使いこなすための応用編にあたる。  
記憶だけでTCAのAPIを決めない。実装前に次を行う。

1. 対象の`Package.resolved`、`Package.swift`、XcodeプロジェクトからTCAとSwift Navigationのバージョンまたはリビジョンを特定する。
2. `ghq list --full-path`で`pointfreeco/swift-composable-architecture`と`pointfreeco/swift-navigation`を探す。
3. 固定リビジョンのソース、テスト、Migration Guideを読む。最新の`main`は移行先の確認に使い、固定リビジョンの挙動より優先しない。
4. リポジトリまたは必要なリビジョンがローカルに存在しない場合は、推測せず取得をユーザーへ依頼する。

主に確認するファイルは次のとおり。

- `Sources/ComposableArchitecture/Observation/ViewAction.swift`
- `Sources/ComposableArchitecture/Reducer.swift`
- `Sources/ComposableArchitecture/Reducer/Reducers/PresentationReducer.swift`
- `Sources/ComposableArchitecture/Documentation.docc/Articles/MigrationGuides/`
- `Tests/ComposableArchitectureMacrosTests/ReducerMacroTests.swift`
- Swift Navigationの`Sources/SwiftNavigation/Binding.swift`

## 作業手順

1. Featureごとに状態の所有者と必要な寿命を決める。
2. Actionを発生元と通知先で分類する。
3. Parent Reducerの処理がChild Stateの同期更新だけで完結し、Child Reducerから同じ更新を行わないなら直接更新する。Child ReducerとParent Reducerが同じ更新を行うならChild Stateのメソッドへ抽出する。具体的な子Actionは原則として送らない。一時的なChildが所有するEffectをChild破棄時に自動キャンセルする必要がある場合は、親子境界とEffectの所有者を再検討してから、専用のTrigger Actionを送る例外を判断する。
4. 表示を閉じたときにChild Effectをキャンセルするか継続するかを決める。
5. Reducer、View、親子のScopeを実装する。
6. Actionの流れとEffectの寿命をテストする。
7. 対象リポジトリの指示に従ってビルドまたはテストする。

曖昧な場合は、次の2点を先に確認する。

- そのイベントを発生させる主体は誰か。
- 画面が消えた後も、状態または処理を残す必要があるか。

## Action Boundaries

Actionは次の順序で分類する。

- `binding`: `BindableAction`による双方向入力。
- `view`: タップ、送信、Viewのライフサイクルなど、Viewが意図を伝える入力。
- `internal`: Dependency、Effect、通知、タイマーからFeatureへ戻る入力。
- 子FeatureのAction: `child`、`rows`など、Reducer合成に必要な入力。
- `destination`または`path`: PresentationとNavigation Stackの入力。
- `delegate`: 子Featureから親Featureへ公開する出力。

`view`、`internal`、`delegate`への分割は設計規約であり、Swiftのアクセス制御ではない。`ViewAction`と`@ViewAction`はView用の`send`を提供し、View内の直接的な`store.send`へ警告を出して規約違反を見つけやすくする。

親は原則として子の`delegate`だけを解釈する。親から子の処理を起動するために、子の`view`、`internal`、専用の処理要求Actionを送らない。Parent Reducerの処理がChild Stateの同期更新だけで完結し、Child Reducerから同じ更新を行わないなら直接更新する。同じ同期更新を目的としてParent ReducerからChild Stateのメソッドを呼ぶのは、Child ReducerとParent Reducerがその更新を共有する場合に限る。一時的なChildが所有するEffectをChild破棄時に自動キャンセルする場合だけ、後述の設計見直しを経て、Parentから専用のTrigger Actionを送る例外を認める。

分類、最小例、レビュー観点は[Action Boundaries](references/action-boundaries.md)を読む。

## Destinationの選択

表示方法ではなく、状態とEffectの寿命から選ぶ。

### 表示と寿命が一致するChild Feature

Child Stateを`Destination`のAssociated Valueとして持ち、親Stateでは`@Presents var destination`を使う。`PresentationReducer`はDestinationが`nil`になると、そのPresentation内で実行中のChild Effectを自動的にキャンセルする。

### 画面を閉じた後も存続するChild Feature

通信、ダウンロード、編集途中の状態などを残す場合は、Child Stateを親Stateの通常プロパティとして持ち、Child Reducerを通常の`Scope`で合成する。`Destination`にはAssociated Valueを持たない表示マーカーだけを置く。

Viewでは、列挙型スコープとSwift Navigationの`Binding.init(_:)`を使い、空Caseの`Optional<Void>`を`Bool`へ変換して`navigationDestination(isPresented:)`へ渡す。表示開始はReducerでDestinationを設定する。`Bool` Bindingへ`true`を書き込んで開始しない。

この構造でも、明示的なキャンセル、親Storeの破棄、`.task { await send(...).finish() }`を所有するViewの消失など、別のキャンセル経路は残る。

### AlertStateとの組み合わせ

TCA 1.25.5以降で、Associated Actionを持つ`AlertState`などの非Feature Stateを`@Reducer enum Destination`へ入れる場合は、`@ReducerCaseIgnored`と明示的な`@CasePathable enum Action`を使う。空の表示マーカーも同じDestinationへ置く場合、そのActionのAssociated Valueは`Never`にする。

具体的なReducer、View、AlertState、テスト観点は[Destinationパターン](references/destination-pattern.md)を読む。

## 親から子Actionを送らない

ActionはReducerのメソッドではなく、ViewやEffectなどで起きた出来事を表す。親Viewまたは親Reducerが`.child(.refresh)`のような具体的な子Actionを生成して送ると、子の実装詳細が親の命令APIになるため、このスキルでは原則として採用しない。

Parent Reducerの処理がChild Stateの同期更新だけで完結し、Child Reducerから同じ更新を行わない場合は、Parent Reducerで直接更新する。その更新のためだけにChild Stateへ親専用のメソッドを追加しない。

Child Stateの更新とともにEffectを起動する場合は、この直接更新ルールの対象外である。基本的にはChild Stateの`mutating`メソッドが`Effect<ChildFeature.Action>`を返し、親Reducerはその出力をReducer合成用のActionへmapする。

親と子の両方から同じ処理を起動する場合は、Child Stateへ`mutating`メソッドを追加する。

- 同期的な状態更新だけなら、戻り値を持たないメソッドにする。
- Effectを起動するなら、`Effect<ChildFeature.Action>`を返す。
- 子ReducerはChild Stateのメソッドを直接呼ぶ。
- 親Reducerも基本的には同じメソッドを呼ぶ。Effectを返す場合は、その出力だけを`.map { .child($0) }`で親Actionへ持ち上げる。

ただし、Parent ReducerからChild Stateのメソッドを呼んで返したEffectはParent側のEffectであり、`ifLet`、Presentation、`forEach`、StackによるChild破棄時の自動キャンセル領域には入らない。Child破棄に連動してEffectを自動キャンセルする必要がある場合は、次を先に再検討する。

- 処理は本当にChildが所有し、閉じた後に継続しなくてよいか。
- Parentまたは永続FeatureがEffectと結果を所有する方が自然ではないか。
- Child Stateを永続化し、表示状態だけをDestinationで管理すべきではないか。
- 明示的なCancellation IDとChildのIdentity照合で、所有権を明確にできないか。
- ParentからChildを命令したくなること自体が、親子境界やFeature分割の不自然さを示していないか。

再検討後も「Effectは一時的なChildが所有し、Child破棄時に自動キャンセルする」が要件なら、TCA 1ではParentから専用のTrigger Actionを`.send(.child(...))`で送る例外を認める。`.send`自体ではなく、Storeへ入り直したActionに対してChild Reducerが返すEffectがChildのキャンセル領域へ入る。Parentが通信を開始してChildのResponse Actionだけを送っても、この自動キャンセルは得られない。子の`view`や`internal`を流用せず、例外だと分かるトップレベルのTrigger Actionを使う。

`Action.child`はReducer合成の境界としてだけ使う。親は前述の例外を除いて具体的な子Action Caseを構築せず、子Reducerの`reduce(into:action:)`も直接呼ばない。TCA 1.25以降ではReducerの直接呼び出しが非推奨であり、現行ソースも共有処理を両Reducerから呼べるヘルパーへ抽出する方法を示している。

判断基準、最小例、Discussion #1952との対応は[親から子Actionを送らない](references/parent-child-communication.md)を読む。

## バージョン境界

- 列挙型スコープはTCA 1.25.0で導入され、主要な修正が1.25.2に入った。
- Alertの明示Actionと空Caseを組み合わせる完全なパターンはTCA 1.25.5以降を使う。
- TCA 1.26.0以降では、`$store.scope(\.$destination, action: \.destination).child`、`Scope(\.child, action: \.child)`、`store.scope(\.child, action: \.child)`形式を優先する。
- TCA 1.25.5では、同じ呼び出しに`state:`ラベルが必要である。
- 空Caseは`Optional<Void>`になるため、`Binding(...)`で`Bool`へ変換する。
- TCA 1.25.0から1.25.4、および1.25未満では、固定リビジョンのMigration GuideとテストにあるAPIを使う。新しい構文をそのまま逆移植しない。

## 検証

最低限、次の挙動をTestStoreで確認する。

- `view`から`internal`を経て状態が更新される。
- 子の`delegate`だけが親の判断へ到達する。
- Parent Reducerだけで完結する同期更新では、Parent Actionから期待するChild Stateへ遷移する。
- Child ReducerとParent Reducerが同じ更新を行う場合は、どちらのActionからも同じChild Stateへ遷移する。
- ParentからTrigger Actionを送る例外では、Child ReducerがEffectを開始し、Child破棄時に自動キャンセルされる。
- 通常のPresentationではDismiss時にChild Effectがキャンセルされる。
- 存続型ChildではDismiss後もChild Stateが残り、Effectの応答を受信できる。
- Alert Actionが親へ届き、空CaseはOpen Actionで設定され、Dismiss Actionで`nil`になる。`Never`にPresented Actionがないことも確認する。

次の構造はコードレビューで確認する。

- Parent Reducerだけで完結し、Child Reducerと共有しないChild Stateの同期更新は直接行い、親専用のChild Stateメソッドを追加していない。
- Child ReducerとParent Reducerが同じ更新を行う場合はChild Stateのメソッドへ抽出し、前述の例外を除いて具体的な子Actionを送っていない。
- ParentからTrigger Actionを送っている場合は、Child破棄時の自動キャンセルが必要であり、Parent所有、永続Child、明示的なキャンセルでは不自然になることを確認している。

コンパイルを伴う検証はリポジトリの`AGENTS.md`に従う。Xcodeでプロジェクトを開いている場合はXcode MCP Toolsを最優先し、次に`xcodebuild`、リソースを持たない純粋なSwift Packageに限って`swift test`または`swift build`を使う。

## 完了時の報告

次を簡潔に示す。

- 採用したAction境界とDestinationの寿命モデル
- 参照したTCAとSwift Navigationのバージョンまたはリビジョン
- 実行したテストとビルド、その結果
- 意図的に残した例外または未検証事項
