---
apply: "docs/qiita/.*"
---

# Qiita 記事共通ルール

## ソースコードURL

ソースコードのURLは、Qiitaで埋め込みウィジェットとして表示できるよう、URLを単独行に置き、その前後をそれぞれ1行以上の空行で区切る。

```markdown
ソースコード:

<https://github.com/owner/repository/tree/main/path>

## 次の見出し
```

- URLを本文と同じ行に書いたり、Markdownリンクへ変換したりしない。
- URLの直前または直後に空行がないと、Qiitaのウィジェット表示にならない。
