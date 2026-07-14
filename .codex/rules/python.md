---
apply: ".*\.py$"
---

# Python コーディング規約 (Python 3.12+)

Python 3.12 以降の機能を最大限活用し、モダンで簡潔なコードを記述する。

## 設計原則 (Design Principles)

コードを記述する際は、以下の原則を常に念頭に置くこと。ただし、これらは設計上の指針（ドクトリン）であり、*
*プロダクションコード内のコメントとして直接記述しないこと**。

### 1. KISS 原則 (Keep It Simple, Stupid)

- 常に最もシンプルな方法で問題を解決する。
- 不必要に複雑なアルゴリズム、過度な抽象化、正規表現によるトリッキーなパースなどを避ける。
- 誰が見ても一目で意図が伝わるコードを優先する。

### 2. YAGNI 原則 (You Ain't Gonna Need It)

- 「将来必要になるかもしれない」という予測に基づいた実装は行わない。
- 現時点で必要な機能だけを、最小限のコードで実装する。
- 未使用のパラメータ、将来のための拡張ポイント、汎用すぎる設計などは排除する。

### 3. Repository パターンとモデル操作

- **Service や UseCase 層で Django モデルを直接操作（クエリ発行、保存など）しない。**
- データベースへのアクセスは必ず **Repository 層** を介して行う。これにより、ビジネスロジックと永続化の仕組みを分離し、テストの容易性とコードの再利用性を高める。
- Repository は「データの集合（コレクション）」として扱い、低レベルなクエリ操作を隠蔽する。
- モデルインスタンスを直接返すのではなく、必要に応じて **Domain Model (Dataclass)** や **Value Object** に変換して返すことを検討する。
- **複数レコードの更新を行う際は、対象を一度 QuerySet やリストとして取得し、属性を書き換えた上で `bulk_update`
  を用いて一括保存することを推奨する。これにより、更新対象と内容を明示的に示し、可読性を高める。**
- **1レコードの更新であっても、一貫性を持たせるために同様の手順（リスト化 + `bulk_update`
  ）で行うことを推奨する。また、条件によって更新対象が1件になる場合（例えば、主キーでの取得後など）であっても、このパターンを適用する。
  **

### 4. Django モデル変更時のマイグレーション

- Django モデルを追加・修正・削除する場合は、`.codex/rules/django.md` のマイグレーション管理に従う。

## 型ヒント (Modern Type Hinting)

### 1. 組み込み型の使用

`typing.List`, `typing.Dict`, `typing.Tuple` などの古い型ヒントは使用せず、組み込みの `list`, `dict`, `tuple` を使用する。

- **良**: `list[str]`, `dict[str, int]`
- **悪**: `List[str]`, `Dict[str, int]`

### 2. Union 型の簡略化 (`|` 演算子)

`typing.Union` や `typing.Optional` は使用せず、`|` 演算子（PEP 604）を使用する。

- **良**: `str | int`, `str | None`
- **悪**: `Union[str, int]`, `Optional[str]`

### 3. typing インポートの最小化

Python 3.12 では、多くの型ヒントが組み込み型や `collections.abc` で代用可能。不要な `typing` モジュールのインポートを避ける。

- `Callable` は `collections.abc.Callable` からインポートする。
- `Iterable`, `Sequence`, `Generator` なども `collections.abc` を優先する。

## インポート

### `__init__.py`

- パッケージ識別のみを目的とする `__init__.py` は空ファイルにする。
- 公開APIの再エクスポートなど、明確な用途がある場合だけ内容を記述する。

### ファイル先頭でのインポート

- すべてのインポートはファイルの先頭にまとめる。
- 関数やメソッド内でのインポート（遅延インポート）は避ける。
- **例外**: 循環インポートが発生する場合のみ、関数内インポートを許可する。

**良い例:**

```
from myapp.domain.valueobject import MyValueObject
from myapp.domain.service import MyService

def my_function():
    obj = MyValueObject()
    return MyService().process(obj)
```

**悪い例:**

```
def my_function():
    from myapp.domain.valueobject import MyValueObject  # 避ける
    from myapp.domain.service import MyService  # 避ける
    obj = MyValueObject()
    return MyService().process(obj)
```

**循環インポートの例外:**

```
# models.py (循環インポート回避のため関数内インポートを使用)
def to_dto(self):
    from myapp.domain.valueobject import MyDTO  # models.py と MyDTO が相互参照する場合
    return MyDTO(...)
```

## docstring (ドキュメント文字列)

- **処理を修正した際は、必ず関連する docstring を最新の状態にアップデートすること。**
- **「単体で自己説明的なコード」** を目指し、必要な背景や責務を docstring やコメントで補う。
- クラス、Enum、Dataclass、Django モデル、または docstring を変更するときだけ、`.codex/rules/references/python-docstring.md` を読む。

## f-string (フォーマット済み文字列リテラル)

- **f-string の中（`{}` 内）で複雑な式を記述しない。**
    - 条件分岐、リスト内包表記、複雑な計算などは f-string の外で事前に変数に代入してから使用すること。
    - コードの可読性を保ち、デバッグを容易にするため、`{}` 内はシンプルな変数参照やプロパティアクセス、単純な関数呼び出しに留める。

**良い例:**

```
labels = [res.label for res in [ph_res, ec_res] if res.label != "適正"]
joined_labels = "・".join(labels)
summary = f"土壌診断の結果、{joined_labels}な状態が見受けられます。"
```

**悪い例:**

```
summary = f"土壌診断の結果、{'・'.join([res.label for res in [ph_res, ec_res] if res.label != '適正'])}な状態が見受けられます。"
```

## Value Object (VO) と Domain Model の責務

- Value Object や Domain Model を作成・変更するときだけ、`.codex/rules/references/python-value-object.md` を読む。

## Domain 層の配置

- `domain/` 配下は `service`、`repository`、`valueobject` だけに限定しない。外部APIや外部ファイルなど、ドメイン処理に必要な入力元を抽象化する場合は `dataprovider` など責務が明確なパッケージを追加してよい。
- ただし、単なる処理結果DTOや表示・保存に渡すだけのデータクラスは `service` に置かず、`domain/valueobject` に配置する。
- `service` はドメイン上の処理手順や計算・集約を担当し、値の入れ物となる dataclass 定義を増やしすぎない。

## 例外設計

- 例外クラスは適切なドメイン（Value Object層など）に配置し、責務を明確にする。

