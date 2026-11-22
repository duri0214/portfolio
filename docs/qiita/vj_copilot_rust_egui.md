# Rustとeguiで、音に合わせて映像候補を提示するVJ支援アプリを作った

## はじめに

DJとVJを兼ねると、音楽の操作をしながら次の映像を探し、その動きを確認して選ぶ必要があります。そこで、Windowsの再生音やLINE / MIC入力をもとに、次に使う映像の候補を提示するデスクトップアプリ `vj-copilot` を作りました。

画面はRustの `eframe` / `egui` で作り、音声入力には `cpal`、周波数解析には `rustfft`、動画の読み込みにはFFmpegを使っています。Backgroundの候補は自動で更新しますが、どの映像をSTAGEに表示するかは人が選びます。透過PNGのForegroundも、配置を確認してから手動で表示します。

この記事では、デモの動かし方、音声から候補を選ぶ仕組み、出力前にForegroundを確認する画面、開発中の判断を紹介します。説明は2026年11月22日時点の `vj-copilot` の `main`（コミット `1027388098ed9c51080ff5fa62b9f2beab212a32`）に基づきます。

ソースコード:

https://github.com/duri0214/vj-copilot/tree/1027388098ed9c51080ff5fa62b9f2beab212a32

> **写真プレースホルダー1**
>
> - 撮影対象: 操作画面と、隣に開いたSTAGEウィンドウを含むPC画面全体。
> - 画面の状態: デモを起動し、Backgroundの動画を選択してSTAGEに表示している状態。
> - 伝えたいこと: 操作画面で候補を選び、別ウィンドウで映像を確認する構成。
> - 代替テキスト: 「候補を並べた操作画面と、選択した映像を表示するSTAGEウィンドウ」。
> - キャプション: 「候補選択と映像表示を別のウィンドウで行う」。

## どんなアプリを目指したか

出発点は「大量の素材から次の映像を探す負荷を減らしたい」という課題でした。[最初の親Issue #4](https://github.com/duri0214/vj-copilot/issues/4) では、まず音の変化に応じた少数の動く候補を見せ、人が1本を選ぶところまでをMVPとしました。検索語やタグの入力、LLMの利用、映像の自動切り替えは前提にしていません。

現在、試せる主な機能は次のとおりです。

- PC再生音、LINE / MIC入力、またはデモの合成音を解析する。
- 有効なBackground素材から最大4本を選び、動くプレビューとして表示する。
- 候補をクリックまたはキーで選び、独立したSTAGEウィンドウに表示する。
- 透過PNGのForegroundをSTAGINGで配置し、`PLAY` でSTAGEに重ねる。
- 音量メーターと、実験的なBPM・拍の推定結果を表示する。

候補の自動提示は、映像の内容や曲名を理解しているわけではありません。音と素材に付けた2つの数値が近いものを選ぶ、試作用の方法です。

## デモを動かす

### 準備と素材の生成

Windowsで、Git、Rust stableのMSVCツールチェーン、`ffmpeg` コマンドを用意します。サンプル動画の生成には、FFmpegの `libx264` エンコーダーも必要です。以降のコマンドはすべてPowerShellで実行します。まず、次を確認します。

```bash:console
git --version
rustc --version
cargo --version
ffmpeg -version
```

次は、`vj-copilot` ディレクトリがまだ存在しない場所で実行する例です。記事の説明と同じ実装を確認できるよう、取得後に対象コミットをチェックアウトします。

```bash:console
git clone https://github.com/duri0214/vj-copilot.git
Set-Location vj-copilot
git switch --detach 1027388098ed9c51080ff5fa62b9f2beab212a32
```

以降はリポジトリのルートで実行します。付属スクリプトで、8本のサンプルMP4とメタデータを生成します。ForegroundのサンプルPNGはリポジトリに2点同梱されています。

```bash:console
.\scripts\generate-background-metadata.ps1
```

このスクリプトは `demo-media/background` にある同名のサンプルMP4と `background-metadata.json` を上書きします。自分の素材や編集済みメタデータがある場所では実行しないでください。別の出力先を使う場合の指定方法はREADMEにあります。

利用手順と必要な環境の詳細:

https://github.com/duri0214/vj-copilot/blob/1027388098ed9c51080ff5fa62b9f2beab212a32/README.md

### 合成音で起動する

入力機器がなくても、次のコマンドで画面と解析を試せます。

```bash:console
cargo run --release -- --demo
```

`--media-dir` の省略時は `demo-media` を読み込みます。デモでは約5秒ごとに周波数と音量を変えた合成PCMを解析へ送り、候補の更新を確認できます。合成音は解析用の入力であり、スピーカーから音を鳴らす機能ではありません。

1. 操作画面のBackgroundタブで、最大4本の動く候補を確認します。
2. 候補をクリックするか `1`〜`4` キーを押すと、そのBackgroundがSTAGEに表示され、候補の自動更新が保留されます。
3. Backgroundタブで `Space` を押すと選択が解除され、候補の自動更新が再開します。
4. STAGEウィンドウを閉じた場合は、操作画面の `OPEN STAGE WINDOW` から再表示できます。

候補が `Nothing` のままなら、MP4と `background-metadata.json` の生成先、FFmpeg、画面に表示される読み込みエラーを確認してください。有効な素材が4本未満の場合は不足分が `Nothing` になります。

> **写真プレースホルダー2**
>
> - 撮影対象: 操作画面の音量・BPM表示とBackground候補の領域。
> - 画面の状態: `--demo` で候補が表示され、1本を選んで自動更新が保留されている状態。
> - 伝えたいこと: 動く候補を比較して人が選び、選択中は候補が入れ替わらないこと。
> - 代替テキスト: 「音量とBPM、Background候補、選択中の候補を示す操作画面」。
> - キャプション: 「候補を選ぶと、その間の自動更新を保留する」。

実音を使う場合は `cargo run --release` で通常起動し、`PC 再生音` または `LINE / MIC` とデバイスを選んで `開始` を押します。PC再生音は、音楽を再生しているWindowsの出力先と同じデバイスを選びます。通常ビルドはWASAPIを使い、ASIO対応版はSDKなどを用意して別途ビルドします。入力デバイスを変更するときは先に停止します。

## BackgroundとForegroundを重ねる

素材フォルダは、背景動画と前景画像で分けています。`--media-dir` を指定しない場合、次の `media-dir` が `demo-media` に相当します。

```text
media-dir/
├─ background/
│  ├─ background-metadata.json
│  ├─ low_dark_01.mp4
│  └─ ...
└─ foreground/
   ├─ neon-orbit-left.png
   └─ neon-prism-right.png
```

Backgroundは `background` 直下のMP4と、その特徴を記述したJSONを使います。次は2本だけを登録する例です。付属スクリプトが生成するファイルには8本が登録されます。

```json:demo-media/background/background-metadata.json
[
  { "file": "low_dark_01.mp4", "energy": 0.2, "brightness": 0.2 },
  { "file": "high_bright_01.mp4", "energy": 0.8, "brightness": 0.8 }
]
```

`file` は同じフォルダ内のファイル名、`energy` と `brightness` は0〜1の数値です。メタデータがないMP4、存在しないファイルを指す項目、重複、範囲外の値、デコードできない動画は除外され、理由が画面に表示されます。動画の値は登録時に与えるもので、アプリが映像内容から自動生成するものではありません。

Foregroundは `foreground` 直下の任意サイズのPNGを使います。透明でない画素を含む画像を読み込み、Backgroundの上に最大1枚を重ねます。操作は次の順です。

1. Foregroundタブで `neon-orbit-left.png` を選び、STAGINGに読み込みます。この時点ではSTAGEの表示は変わりません。
2. STAGING上でドラッグして位置を調整し、必要に応じて `Y SPIN ON/OFF` を切り替えます。
3. `PLAY` を押すと、その素材・位置・回転設定がSTAGEに反映されます。
4. 次の `neon-prism-right.png` を選ぶと、前のForegroundをSTAGEに残したまま次の配置を確認できます。再度 `PLAY` を押すと切り替わります。
5. プレビューがない出力中は `STOP` でForegroundを消せます。ForegroundタブまたはSTAGEウィンドウで `Space` を押した場合も、Foregroundのプレビューと出力を解除し、Backgroundの選択は維持します。

同じForegroundカードの再クリックは、STAGINGのプレビューだけを解除します。素材ごとの位置と回転設定はアプリの起動中に保持されますが、ファイルには保存されません。

> **写真プレースホルダー3**
>
> - 撮影対象: ForegroundタブのSTAGINGとSTAGEウィンドウ。
> - 画面の状態: 左側のサンプルをSTAGEに表示したまま、右側のサンプルをSTAGINGで選び、別の位置へドラッグした状態。
> - 伝えたいこと: 次の素材の配置を調整しても、`PLAY` を押すまでは現在のSTAGE表示が維持されること。
> - 代替テキスト: 「STAGEに表示中の画像と、STAGINGで配置中の次の画像」。
> - キャプション: 「出力中の前景を残したまま、次の前景を配置する」。

> **写真プレースホルダー4**
>
> - 撮影対象: STAGEウィンドウとForegroundの操作欄。
> - 画面の状態: 写真3のSTAGINGから `PLAY` を押し、右側のサンプルがBackgroundに重なって `STOP` が表示された状態。
> - 伝えたいこと: 確定操作で前景が切り替わり、停止操作ができること。
> - 代替テキスト: 「背景動画に前景画像を重ねたSTAGEとSTOPボタン」。
> - キャプション: 「PLAYで配置をSTAGEへ反映し、STOPで前景を消す」。

## 音から候補を選ぶ仕組み

大まかな流れは次のようになっています。

```text
PC再生音 / LINE・MIC / デモの合成PCM
    ↓
音声の特徴量を計算し、直近1秒を平均
    ↓
素材のenergy・brightnessと距離を比較
    ↓
最大4本を動く候補として表示
    ↓
人が選択 → STAGEに表示
```

音声側では、200ミリ秒ごとにRMS音量とスペクトル重心を求めます。スペクトル重心は周波数成分の重み付き平均で、高い周波数の成分が強いほど大きくなる、音色の明るさの目安です。RMSをdBFSに変換して `(dBFS + 60) / 60` で正規化した `energy` と、重心を8,000 Hzで割った `brightness` をそれぞれ0〜1に収め、直近5区間、約1秒の平均を候補選びに使います。

ここでの音の `brightness` と、素材に付けた映像の `brightness` は同じ物理量ではありません。「明るい音には明るい映像が合うかもしれない」という仮説を試すための対応付けです。直近の区間に無音が含まれる場合や入力が止まった場合は、古い特徴量で候補を更新し続けず、現在の候補を保持します。

音声解析の実装:

https://github.com/duri0214/vj-copilot/blob/1027388098ed9c51080ff5fa62b9f2beab212a32/src/domain/service/audio_analysis.rs

ランキングは、音と各素材の2つの値について、差の二乗の和を求めて距離が小さい順に並べます。同じ距離ならファイル名順です。読み込めた有効素材をすべて比較し、上位4本までを候補にします。表示中の候補が次の上位にも残るときは、同じ枠を維持し、入れ替わる素材だけを差し替えます。候補更新は約2秒間隔で、選択中は保留されます。

ランキングと表示枠の実装:

https://github.com/duri0214/vj-copilot/blob/1027388098ed9c51080ff5fa62b9f2beab212a32/src/domain/service/ranking.rs

https://github.com/duri0214/vj-copilot/blob/1027388098ed9c51080ff5fa62b9f2beab212a32/src/domain/service/candidate_state.rs

音量メーターは候補検索とは別に約25ミリ秒の区間で更新します。BPMはFFTから求めた音の変化と自己相関を使って60〜200 BPMを推定し、拍ランプとともに表示します。推定は実験的で、半分や倍のテンポになる場合があります。BPMは候補の距離計算には使わず、映像の拍同期も行いません。

## 動画と前景表示の実装

動画は読み込み時にFFmpegで先頭最大3秒を320×180、15 fpsのRGBAフレームに変換し、メモリに保持します。候補もSTAGEも、そのフレームをループ表示します。長尺動画を最後まで再生するプレーヤーではなく、音声トラックも出力しません。素材数を増やすと、読み込み時間やメモリ使用量も増えます。

Foregroundは透明度を使って合成します。画像の透明でない画素について、アルファ値で重み付けした座標の重心を求め、それを支点に横方向の幅を周期的に変えることで、Y軸回転風の動きを作っています。完全に透明なPNGは重心を求められないため除外します。

音声入力のコールバックはサンプルを有界バッファに渡し、解析は別のworkerで行います。バッファがいっぱいのときは待機せずサンプルを破棄し、欠落や入力の中断を検出した際は解析履歴をリセットします。画面更新や音声入力の処理と、特徴量計算の責務を分けるためです。

素材の読み込みと画面描画の実装:

https://github.com/duri0214/vj-copilot/blob/1027388098ed9c51080ff5fa62b9f2beab212a32/src/infra/media.rs

https://github.com/duri0214/vj-copilot/blob/1027388098ed9c51080ff5fa62b9f2beab212a32/src/ui/app.rs

## 開発中に変えたこと

IssueとPRを追うと、最初の小さな候補選択から、操作時に必要な画面を少しずつ追加したことが分かります。

| 時期 | 判断と変更 | 記録 |
| --- | --- | --- |
| 2026年9月 | 音声から最大4本の動く候補を提示し、人が選択するMVPを実装。PC再生音の取得も追加した | [Issue #4](https://github.com/duri0214/vj-copilot/issues/4)、[PR #5](https://github.com/duri0214/vj-copilot/pull/5) |
| 2026年9月 | BPM・拍ランプと任意のASIO入力を追加。BPMは選択の参考表示とした | [Issue #7](https://github.com/duri0214/vj-copilot/issues/7)、[PR #8](https://github.com/duri0214/vj-copilot/pull/8) |
| 2026年9月 | Backgroundと静止PNGの二層合成を追加し、STAGEを別ウィンドウに分離した | [PR #13](https://github.com/duri0214/vj-copilot/pull/13)、[PR #15](https://github.com/duri0214/vj-copilot/pull/15) |
| 2026年9月 | 候補の母集団を当初の最大8本から全有効素材へ広げ、表示は最大4本のままにした。メタデータのファイル名も分かりやすく変更した | [PR #16](https://github.com/duri0214/vj-copilot/pull/16)、[PR #18](https://github.com/duri0214/vj-copilot/pull/18) |
| 2026年9月〜10月 | Foregroundを任意サイズにし、位置調整と、出力前のSTAGING / `PLAY` を追加した | [PR #19](https://github.com/duri0214/vj-copilot/pull/19)、[PR #21](https://github.com/duri0214/vj-copilot/pull/21) |

当初のForegroundは画面と同じサイズのPNGを前提にしていました。その後、素材自体の大きさや透明領域を使えるようにし、さらに「選んだ時点でSTAGEを変える」のではなく、位置を決めてから `PLAY` する操作へ発展させています。古いIssueやPRの記述には、後の変更で置き換わった仕様もあるため、利用時は現行のREADMEとコードを参照してください。

また、実装前に既存VJソフトを比較する[Issue #3](https://github.com/duri0214/vj-copilot/issues/3) は、プロダクトを先に作ったとしてクローズされています。実機比較が完了したことを示す記録ではありません。[PR #5](https://github.com/duri0214/vj-copilot/pull/5) でも、実際の音楽とDJ操作を並行した3回の候補選択評価は未実施と記されています。サンプルで動くことと、推薦品質や操作負荷の改善を実証することは分けて考える必要があります。

## 現在の範囲と、今後検討できること

現在のSTAGEは独立したウィンドウとしてサブディスプレイやプロジェクターへ移動できますが、専用の映像出力プロトコルを実装したものではありません。Foregroundの同時表示は1枚で、位置や回転設定はアプリ終了後には復元されません。

元のIssueでは、LLM / VLMを使った素材検索や意味的なメタデータ生成なども将来の拡張案として挙げられています。これらは現行の候補選択には含まれず、実施時期が決まった機能として扱っていません。曲名やアーティストの自動認識、BPMに合わせた映像同期、自動切り替えも現在の機能には含まれません。

実際の使いやすさを評価するには、実音楽とDJ操作を並行し、候補を選ぶまでの時間や迷い、映像との相性を記録する必要があります。ASIO実機入力やWASAPIとの物理遅延比較についても、[PR #8](https://github.com/duri0214/vj-copilot/pull/8) の確認時には対応機器がなく未検証と記録されています。

音の特徴を使って候補を絞り、出力は人が決める。まずはその流れを小さく実装し、Foregroundを出す前の確認や画面分離を後から加えられたことが、この試作の成果です。
