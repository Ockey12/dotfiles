---
name: effective-composable-architecture
description: The Composable Architecture(TCA)のFeatureを設計、実装、レビュー、リファクタリングするときに使う。Action Boundaries(view、trigger、internal、delegate、binding、Child FeatureのAction)、ViewAction、Parent FeatureからChild Featureへ入力したい場合の選択肢と判断基準、TCA 1からTCA 2のTrigger移行、EffectとDependency、Destination、AlertState、Sheet、NavigationStack、画面を閉じた後も処理を継続するChild Featureのライフサイクル設計を扱う。
---

# Effective Composable Architecture

このスキルでいうFeatureは、TCA 1で`Reducer`として実装する単位を指す。Feature間の関係はParent FeatureとChild Featureと表記する。`Reducer`は`@Reducer`、`ReducerOf`、`BindingReducer`、`PresentationReducer`など、TCA 1のAPI名や型名を示す場合だけ使う。

## 目的

TCAのライブラリ規則だけでは統一できない詳細な実装方針を揃える。パフォーマンス、ライフサイクル、TCA 2への移行を考慮して実装方針を決定している。

Featureの入力境界、状態の所有権、Effectの寿命をコードから説明できる設計にする。特定のアプリ固有の名前や前提を例へ持ち込まない。

## 成果条件

- View、Effect、Child Feature、Parent Featureから届くActionを分類する。
- TCA 1のローカル規約である`trigger`境界と、TCA 2の公式`@Trigger`を区別する。
- Parent FeatureからChild Featureへ入力したい場合に、Stateの直接更新、同期処理の共有、Effectの所有者の変更、Dependencyの共有、TCA 1の`trigger`を選び分ける。
- 画面の表示期間とChild Featureの寿命が一致するかを判断する。
- 対象プロジェクトが固定するTCAのAPIで実装する。
- 境界とライフサイクルをTestStoreで検証する。
- 変更理由と一次ソースを報告する。

## 一次ソースの確認

TCAの実装またはAPIレビューでは、`pfw-composable-architecture`スキルを使用できる場合、最初に参照する。このスキルはTCAをさらに使いこなすための応用編として使う。記憶だけでAPIを決めず、次を行う。

1. 対象の`Package.resolved`、`Package.swift`、XcodeプロジェクトからTCAと関連ライブラリ(swift-navigationやswift-dependenciesなど)のバージョンまたはリビジョンを特定する。
2. この後の条件から必要なreferenceを選び、該当ファイルを最後まで読む。
3. referenceの一次ソース一覧を手掛かりに、ローカルcloneの固定リビジョンにあるソース、テスト、Migration Guideを確認する。
4. 最新の`main`やTCA 2開発版を移行先の確認だけに使い、対象プロジェクトの固定リビジョンより優先しない。
5. 必要なリポジトリまたはリビジョンがローカルに存在しない場合、推測せずユーザーへcloneを依頼する。

## 命名
Stateのプロパティのうち、Viewから参照するものはユーザーからどう見えるのかを軸に命名する。

例えば、通信に失敗したら再読み込みボタンを表示する場合、その状態を表すBool型プロパティの命名は以下にする。
- 推奨: `isShowingReloadButton`
- 非推奨: `isFailedCommunication`

## 作業手順

1. [一次ソースの確認](#一次ソースの確認)を行う。
2. Actionの発生元と通知先、StateとEffectの所有者、必要な寿命を明らかにする。
3. この後の条件に該当するreferenceをすべて読む。
4. referenceと固定リビジョンの一次ソースに従って実装する。
5. 読んだreferenceのテスト観点とレビュー観点を使って検証する。
6. 対象リポジトリの指示に従ってビルドまたはテストする。

## TestStoreの検証方針

TestStoreでは原則として`exhaustivity = .off`を使用しない。送受信されるAction、Stateの変化、実行中のEffectの完了またはキャンセルを網羅的に検証する。例外的に使用する場合は、その理由と未検証範囲を明示する。

## Referenceの選択

### Action Boundaries

Actionの追加、命名、並び、`ViewAction`、Binding、Parent FeatureとChild FeatureのAction境界を実装またはレビューする場合に読む。

Action境界は、次の固定順序で分類し、列挙する。

- `view`: ボタンタップやViewのライフサイクルなど、View起点のイベントを伝える入力。
- `trigger`: 別FeatureがChild Feature所有の処理を起動する入力。TCA 1でのみ使うローカル規約であり、TCA 2の`@Trigger`への移行元となる。
- `internal`: Dependency、Effect、通知、タイマーからFeatureへ戻る、同一Feature内に閉じた入力。
- `delegate`: Child FeatureからParent Featureへ公開する出力。
- `binding`: `BindableAction`による双方向入力。

Feature合成用のActionは、上記5境界の後に列挙する。

- Child FeatureのAction: `child`、`rows`など、Feature合成に必要な入力。
- `destination`または`path`: PresentationとNavigation Stackの入力。

分類手順、宣言順、`Reduce`での分岐、ViewとFeature間の境界、最小例、テスト観点、レビュー観点は[Action Boundaries](references/action-boundaries.md)を読む。

### Destinationパターン

次のいずれかに該当する場合、[Destinationパターン](references/destination-pattern.md)を読む。

- `Destination`、`@Presents`、Sheet、`navigationDestination`、Navigation Stackを追加または変更する。
- 画面のDismissやPopに合わせてChild FeatureのStateまたはEffectを終了するか、画面を閉じた後も残すかを判断する。
- 列挙型スコープ、空のDestination Case、Optionalから`Bool`へのBindingを扱う。
- `AlertState`をFeature Caseまたは空Caseと同じDestinationへ入れる。
- Presentation、永続するChild Feature、Alertのテストまたはレビューを行う。

### Parent FeatureとChild Featureの通信

次のいずれかに該当する場合、[Child FeatureへActionを送りたい場合の選択肢と判断基準](references/parent-child-communication.md)を読む。

- Parent FeatureがChild FeatureのStateを更新する、または同じState更新を両Featureで共有する。
- Parent FeatureからChild Feature所有の処理を起動したい、またはChild FeatureのActionを構築したい。
- State、Effect、Dependency、Cancellation IDの所有者を判断する。
- TCA 1の`trigger`、Presentationと通常の`Scope`におけるキャンセル、Action送信の性能を扱う。
- `Effect.map`、Featureの`reduce(into:action:)`直接呼び出し、TCA 2の公式`Trigger`への移行を扱う。

### 複数のreferenceを読む場合

複数の条件に該当する場合、対応するreferenceをすべて読む。Presentation内のChild FeatureへParent Featureから入力する設計では、3つのreferenceすべてが対象になる。

## 完了時の報告

次を簡潔に示す。

- 採用したAction境界とDestinationの寿命モデル
- 参照したTCAとSwift Navigationのバージョンまたはリビジョン
- 実行したテストとビルド、その結果
- 意図的に残した例外または未検証事項
