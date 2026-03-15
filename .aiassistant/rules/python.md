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

## インポート
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
- **「単体で自己説明的なコード」** を目指し、必要な背景や責務を docstring やコメントで補う。
- レビュアーがドメイン知識を持っていなかったり、特定のファイル順（ファイルツリーの上から順など）に読み進めていない場合でも、そのクラスやメソッドを見るだけで役割が完結して理解できるように記述する。
- 特に、単一のエンティティに対する処理なのか、セッションやリスト全体の集合に対する処理（集計・総合評価・スコアの蓄積など）なのかを冒頭に明記し、前後の文脈を追わなくても役割が即座に判別できるようにする。
- 属性（Attributes）や引数（Args）、戻り値（Returns）のセクションを適切に使い、IDEのホバー表示で内容が完結するように記述する。

## 例外設計
- 例外クラスは適切なドメイン（Value Object層など）に配置し、責務を明確にする。
