# Python docstring 詳細規約

クラス、Enum、Dataclass、Django モデル、または docstring を変更するときだけ読む。

- docstring を更新するときは、引数、戻り値、副作用、および処理の意図（なぜそのように実装されているか）が現状と一致していることを確認する。
- 列挙型（Enum）や定数の変更があった場合、Attributes の説明も併せて更新する。
- レビュアーがドメイン知識を持っていなかったり、特定のファイル順（ファイルツリーの上から順など）に読み進めていない場合でも、そのクラスやメソッドを見るだけで役割が完結して理解できるように記述する。
- 特に、単一のエンティティに対する処理なのか、セッションやリスト全体の集合に対する処理（集計・総合評価・スコアの蓄積など）なのかを冒頭に明記し、前後の文脈を追わなくても役割が即座に判別できるようにする。
- 属性（Attributes）や引数（Args）、戻り値（Returns）のセクションを適切に使い、IDEのホバー表示で内容が完結するように記述する。
- 属性（状態）を持つクラス（Dataclass、Enum、Django モデルなど）の docstring には、必ず `Attributes` セクションを記述する。
  - Repository や Service など、属性を持たないクラスについては `Attributes` セクションを省略して良い。
  - 継承関係がある場合、基底クラスで共通属性を記述し、サブクラスではそのクラス固有の属性（定数を含む）を記述する。
- Django モデルの場合、各フィールドに必ず `verbose_name` を設定し、docstring に `Attributes` セクションを記述して日本語項目名との対応を明記する。
  - DB上のカラム名（英語）と業務上の項目名（日本語）の対応がコード内で完結して把握できるようにし、可読性と保守性を向上させる。
- Enum の場合、クラスレベルの `Attributes` セクションに各メンバーの定義と意味を記述する。
  - IDE のホバー時にその値の意味が即座に把握できるようにするため。

## Enum の例

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

## 一般的なクラスの例

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
