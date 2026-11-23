# UTM座標変換の調査

写真の冒頭2ページで確認できる旧プログラムの機能は、UTMと緯度経度の双方向変換、GEOREFの表示、UTMワールドモデルの選択・表示である。画面制御と入力制御、楕円体パラメータを持つC言語のコンソールプログラムとして記載されている。残りの写真の全文書き起こしと、計算式・入力制約・各モデルの詳細な分析は未完了であり、旧プログラムとの互換性は未検証である。原資料のコードは収録していない。

## 今回の実装

既存依存の [pyproj](https://pyproj4.github.io/pyproj/stable/api/transformer.html) と [PROJのUTM投影](https://proj.org/en/stable/operations/projections/utm.html) を用い、WGS84の緯度経度とUTMの相互変換を提供する。測地系の変換や旧モデルの再現は行わない。GEOREFとコンソール画面も対象外とする。

`soil_analysis.domain.service.utm` の `to_utm(longitude, latitude, zone, northern)` は経度・緯度を度で受け、東距・北距をメートルで返す。`from_utm(easting, northing, zone, northern)` は逆順に変換し、経度・緯度を返す。ゾーン（1〜60）と北半球かどうかは呼び出し側が指定する。ゾーンは自動選択せず、座標が指定ゾーンに適合するかも検証しないため、呼び出し側で確認する。UTMの緯度範囲外と非有限値は拒否する。

旧資料の残りの分析、旧測地モデルとの対応、GEOREFの必要性や旧版との精度比較は今後の課題である。
