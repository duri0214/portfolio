---
apply: ".*\.py$"
---

# Python コーディング規約 (Python 3.12+)

Python 3.12 以降の機能を最大限活用し、モダンで簡潔なコードを記述する。

## 設計原則 (Design Principles)

コードを記述する際は、以下の原則を常に念頭に置くこと。ただし、これらは設計上の指針（ドクトリン）であり、**プロダクションコード内のコメントとして直接記述しないこと**。

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
- **一般的なクラスや Enum の docstring には、必ず `Attributes` セクションを記述する。** これにより、呼び出し側や利用側で変数やプロパティにホバーした際、その役割や型、意味が即座に把握できるようにする。
- Enum の場合、クラスレベルの `Attributes` セクションに詳細を記述することで、IDEのホバー時にその値の意味が把握できるようにする。

**Enum の良い例:**
```
class SessionState(Enum):
    """
    なぞなぞセッションの状態管理。

    Attributes:
        RIDDLE_START: 問題を出題している状態。
        WAIT_ANSWER: ユーザーからの回答を待機している状態。
        FINISHED: 全ての問題が終了し、最終評価が完了した状態。
    """

    RIDDLE_START = "RIDDLE_START"

    WAIT_ANSWER = "WAIT_ANSWER"

    FINISHED = "FINISHED"
```

**一般的なクラスの良い例:**
```
class UserProfile:
    """
    ユーザーのプロフィール情報を保持するクラス。

    Attributes:
        user_id: ユーザーの一意識別子。
        nickname: 表示用の名前。
        is_active: アカウントが有効かどうか。
    """

    def __init__(self, user_id: int, nickname: str, is_active: bool = True):
        self.user_id = user_id
        self.nickname = nickname
        self.is_active = is_active
```

## Value Object (VO) と Domain Model の責務
- Value Object は不変（Immutable）であり、それ自体が特定の意味や計算ロジックを持つべきである。
- ただし、VO に外部の状態（DBの状態やグローバルなフラグなど）に依存する複雑な遷移ロジックを持たせるのは避ける。
- 状態遷移などの「振る舞い」が複雑になる場合は、UseCase や Service でそのフローを制御し、VO はあくまで「現在の状態」や「単純な次の候補」を示す役割に留める。
- VO 内で他のドメインサービスやリポジトリを呼び出すことは厳禁とする。

## 例外設計
- 例外クラスは適切なドメイン（Value Object層など）に配置し、責務を明確にする。
