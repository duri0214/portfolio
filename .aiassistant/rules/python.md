---
apply: ".*\.py$"
---

# Python コーディング規約 (Python 3.12+)

Python 3.12 以降の機能を最大限活用し、モダンで簡潔なコードを記述する。

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

## 命名規則
- ローカル変数は `snake_case` を徹底する。

## 例外設計
- 例外クラスは適切なドメイン（Value Object層など）に配置し、責務を明確にする。
