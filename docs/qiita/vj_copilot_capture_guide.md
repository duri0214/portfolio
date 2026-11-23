# Snipping ToolとFFmpegでQiita用のGIFを作る

これは `vj-copilot` の紹介記事にあるGIFプレースホルダーを埋めるための執筆用メモです。Windows 11のSnipping Toolで画面を録画し、すでにデモの準備で使っているFFmpegでGIFに変換します。GIFには音声は入りません。

## 1. 録画する

1. `vj-copilot` のデモを起動し、録画したい画面を用意します。操作画面とSTAGEの両方を録る場合は、同じモニター内に並べます。
2. Snipping Toolを開き、録画ボタンと「新規」を選びます。`Windows` + `Shift` + `R` でも録画の範囲選択を開けます。
3. 画面の必要な範囲をドラッグして「開始」を押します。操作が分かる長さを目安に録画し、「停止」を押します。
4. 表示された録画を保存し、ファイル名を `vj-demo.mp4` にします。この例ではWindowsのユーザーフォルダーへ保存します。保存先を開くには、エクスプローラーのアドレス欄に `%USERPROFILE%` と入力できます。同名の録画を残したい場合は別名で保存し、後のコマンドでもその名前を使います。

GIF 2は、Background候補が動いて更新された後に1本を選び、選択後もしばらく録って、候補の自動更新が保留される様子を見せます。GIF 3は、STAGEに前景を出したまま、別の前景をSTAGINGで選んで配置し、`PLAY` で切り替えるところを録ります。

録画機能の操作は [MicrosoftのSnipping Toolの説明](https://support.microsoft.com/ja-jp/windows/apps/use-snipping-tool-to-capture-screenshots)も参照できます。

## 2. MP4をGIFに変換する

PowerShellを開き、録画ファイルを保存したユーザーフォルダーへ移動して、次を実行します。

```bash:console
cd $env:USERPROFILE
ffmpeg -i .\vj-demo.mp4 -filter_complex '[0:v]fps=10,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse' -loop 0 .\vj-demo.gif
```

`fps=10` は1秒あたり10コマ、`scale=800:-1` は縦横比を保って横幅を800ピクセルにする指定です。録画の色からGIF用のパレットを作って変換し、`-loop 0` で繰り返し再生します。出力された `vj-demo.gif` をブラウザーなどで開き、動きと文字の読みやすさを確認してください。

入力と出力のファイル名は別にしてください。同じ名前の出力ファイルがすでにある場合、FFmpegは上書きするか確認します。残したいファイルであれば `n` で中止し、出力名を変えて再実行します。別の場所や名前で録画した場合は、その保存先に移動し、コマンド内のMP4名を実際のファイル名に置き換えてください。

## 3. Qiitaへ貼り付ける

Qiitaの画像アップロードはGIFに対応しており、上限は1ファイル10 MB、月合計100 MBです。作成したGIFをエクスプローラーのプロパティで確認し、大きすぎる場合は録画を短くするか、変換コマンドの `fps=10` を `fps=8`、`scale=800` を `scale=640` のように小さくして再作成します。

記事の編集画面へGIFをドラッグ＆ドロップし、挿入された画像記法に内容が伝わる代替テキストを付け、短いキャプションも添えます。プレビューでGIFが動くことと、操作が読み取れることを確認してから、該当するプレースホルダーを置き換えます。制限やアップロード方法の最新情報は [Qiitaの画像アップロード案内](https://help.qiita.com/ja/articles/qiita-image-upload)を参照してください。
