---
name: obsidian-create-file
description: MarkdownメモツールObsidianの管理下にファイルを追加する際に使用する。ただし、プロンプトで明示的にこのSkillを使うよう指定された場合だけ使用する。特に、翻訳タスクでは別のファイル生成ルールがあるため、このSkillは使わないこと。
---

# Obsidian Create File

## 原則
Obsidianでは、ファイル名に以下の記号を使えない。
- `/`
- `#`
- `[`
- `]`
- `|`

## ファイル作成の手順

作成するファイルの名前を<ファイル名>とする。
ファイル名も含めたObsidian内でのパスを`FILE = "AIConversationHistory/<ファイル名>.md"`とする。

また、`Vault = "Ockey"`とする。

### 1. TemplaterプラグインでMarkdownファイルを生成する

```bash
obsidian vault="$VAULT" templater:create-from-template \
  template="_Configure/Templates/Note" \
  file="$FILE"
```

### 2. frontmatterにタグを設定する

```bash
obsidian vault="$VAULT" property:set \
  path="$FILE" \
  name="tags" \
  value="byAI" \
  type=list
```

### 3. 本文末尾に内容を追加する

```bash
obsidian vault="$VAULT" append \
  path="$FILE" \
  content="$CONVERSATION"
```
