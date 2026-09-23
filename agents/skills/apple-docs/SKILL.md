---
name: apple-docs
description: SwiftUIやUIKitなど、Appleプラットフォームの開発用ドキュメントを参照する際の手順を示す。
---

## コードに関するドキュメント

以下の優先度でドキュメントを参照する。

1. Xcode MCPの`Documentation Search`機能で、対象APIのドキュメントを参照する。
2. 1.で対象APIのドキュメントが見つからない場合は、Webでドキュメントを検索する。その際、Appleのドキュメントは通常だとJSを動作させないと閲覧できないが、URLの末尾に`.md`を付けることで、マークダウン形式で見られる。例えば、`https://developer.apple.com/documentation/swiftui`はそのままだと開けないが、`https://developer.apple.com/documentation/swiftui.md`とすることでマークダウン形式で開ける。
3. 2.でも対象APIのドキュメントが見つからない場合は、sosumi.ai MCPでドキュメントを参照する。

## デザインに関するドキュメント

WebでHuman Interface Guidelinesを検索する。その際、URLに以下の2つの変更を加えることで、マークダウン形式で見られる。
- `design`の前に`/tutorials/data/`を加える
- 末尾に`.md`を加える

例えば、`https://developer.apple.com/design/human-interface-guidelines/toolbars`を`https://developer.apple.com/tutorials/data/design/human-interface-guidelines/toolbars.md`にして検索する。
