import os

import matplotlib

matplotlib.use("Agg")  # GUIバックエンドを使わずにヘッドレスモードに設定
import matplotlib.pyplot as plt
import numpy as np
from django.core.management.base import BaseCommand

from soil_analysis.models import SoilHardnessMeasurement


class SoilHardnessPlotter:
    """土壌硬度データをプロットするクラス"""

    def __init__(self, output_dir="."):
        """初期化

        Args:
            output_dir: 出力ディレクトリ（デフォルトはカレントディレクトリ）
        """
        self.output_dir = output_dir

        # 日本語フォント設定
        plt.rcParams["font.family"] = ["IPAexGothic"]

    @staticmethod
    def _get_measurement_data(land_ledger_id=None):
        """測定データの取得

        Args:
            land_ledger_id: 特定の圃場台帳ID

        Returns:
            dict: 圃場台帳IDごとのデータ
        """
        # データ取得のクエリセット
        queryset = SoilHardnessMeasurement.objects.select_related(
            "land_ledger__land__company", "land_ledger__land", "land_block"
        ).order_by("depth")

        if land_ledger_id:
            queryset = queryset.filter(land_ledger_id=land_ledger_id)
        else:
            # land_ledger_idがNoneの場合は、land_ledgerが設定されているデータのみを対象とする
            queryset = queryset.filter(land_ledger__isnull=False)

        # 圃場台帳ごとにグループ化
        land_ledgers = queryset.values_list("land_ledger", flat=True).distinct()

        return {"queryset": queryset, "land_ledgers": land_ledgers}

    @staticmethod
    def _get_land_info(ledger_data):
        """圃場情報の取得

        Args:
            ledger_data: フィルタリングされた測定データ

        Returns:
            tuple: (会社名, 圃場名, サンプリング日付)
            または存在しない場合はNone
        """
        if not ledger_data.exists():
            return None

        # 圃場情報取得
        first_record = ledger_data.first()
        company_name = first_record.land_ledger.land.company.name
        land_name = first_record.land_ledger.land.name
        sampling_date = first_record.land_ledger.sampling_date.strftime("%Y%m%d")

        return company_name, land_name, sampling_date

    def _save_plot(self, fig, company_name, land_name, sampling_date, plot_type):
        """プロットを保存する

        Args:
            fig: matplotlib図オブジェクト
            company_name: 会社名
            land_name: 圃場名
            sampling_date: 採取日
            plot_type: プロットタイプの文字列

        Returns:
            str: 保存したファイルパス
        """
        import re

        # ファイル名の作成
        filename = (
            f"soil_hardness_{company_name}_{land_name}_{sampling_date}_{plot_type}.png"
        )

        # Windowsで無効な文字を除去/置換
        # 無効な文字: < > : " | ? * \ /
        invalid_chars = r'[<>:"|?*\\/]'
        filename = re.sub(invalid_chars, "_", filename)

        # 連続するアンダースコアを1つにまとめる
        filename = re.sub(r"_+", "_", filename)

        # ファイル名の長さを制限（拡張子を含めて255文字以下）
        if len(filename) > 250:  # .pngを考慮して少し余裕を持たせる
            base_name = filename[:-4]  # .pngを除く
            filename = base_name[:246] + ".png"

        # 末尾のピリオドやスペースを除去（Windowsでは問題となる）
        filename = filename.rstrip(". ")
        if not filename.endswith(".png"):
            filename += ".png"

        save_path = os.path.join(self.output_dir, filename)

        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        return save_path

    def plot_3d_surface(self, land_ledger_id=None, folder=None):
        """土壌硬度データを3D表面プロットとして描画

        元のGitHubコードを参考にして、X軸に圃場内位置、Y軸に深度、Z軸に圧力値として表示

        Args:
            land_ledger_id: 特定の圃場台帳ID（Noneの場合は全データ）
            folder: 特定のfolderのみをフィルタ
        """
        # データ取得
        data = self._get_measurement_data(land_ledger_id)
        queryset = data["queryset"]

        # folderでさらにフィルタ
        if folder:
            queryset = queryset.filter(folder=folder)

        # フォルダごとに1つのプロットのみを作成するため、最初のland_ledgerの情報を使用
        first_ledger_data = queryset.first()
        if not first_ledger_data:
            return

        # 圃場情報取得（最初のレコードから）
        company_name = first_ledger_data.land_ledger.land.company.name
        land_name = first_ledger_data.land_ledger.land.name
        sampling_date = first_ledger_data.land_ledger.sampling_date.strftime("%Y%m%d")

        # folderが指定されている場合はタイトルに追加
        if folder:
            land_name = f"{land_name}_{folder}"

        # プロット作成処理を1回だけ実行
        self._create_single_plot(
            queryset, company_name, land_name, sampling_date, folder
        )

    def _create_single_plot(
        self, ledger_data, company_name, land_name, sampling_date, folder
    ):
        """単一のプロットを作成する（重複実行を避けるため分離）"""
        # 圃場内位置の組み合わせを取得（land_blockでグループ化してdistinct）
        location_combinations = list(
            ledger_data.values_list("land_block__name", flat=True)
            .distinct()
            .order_by("land_block__name")
        )

        # 深度のリストを取得
        depths = sorted(ledger_data.values_list("depth", flat=True).distinct())

        # 圧力データを2次元配列に格納（locations x depths）
        pressure_data = np.zeros((len(location_combinations), len(depths)))
        pressure_data.fill(np.nan)

        for data_point in ledger_data:
            block_name = data_point.land_block.name

            try:
                location_idx = location_combinations.index(block_name)
                depth_idx = depths.index(data_point.depth)
                pressure_data[location_idx, depth_idx] = data_point.pressure
            except ValueError:
                continue  # データが見つからない場合はスキップ

        # 3Dプロット作成
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        # X軸: 圃場内位置のインデックス（0, 1, 2, ...）
        # Y軸: 深度（cm）
        x = np.arange(len(location_combinations))
        y = np.array(depths)
        x, y = np.meshgrid(x, y)

        # Z軸: 圧力データ（転置して深度×位置の形にする）
        z = pressure_data.T

        # 3D表面プロット
        surf = ax.plot_surface(x, y, z, cmap="viridis", alpha=0.8)

        # X軸の目盛りラベルを圃場内位置の組み合わせに設定
        ax.set_xticks(np.arange(len(location_combinations)))
        ax.set_xticklabels(location_combinations)

        # 軸ラベル
        ax.set_xlabel("圃場内位置")
        ax.set_ylabel("深度 (cm)")
        ax.set_zlabel("圧力 (kPa)")

        # タイトル
        ax.set_title(f"{company_name} - {land_name} 土壌硬度分布 ({sampling_date})")

        # カラーバー
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label="圧力 (kPa)")

        # 保存（1回のみ実行）
        self._save_plot(fig, company_name, land_name, sampling_date, "3d_surface")


class Command(BaseCommand):
    help = """
    土壌硬度測定データから3D表面プロットを生成するバッチコマンド

    各folder（圃場計測データ）ごとに3D表面プロットを作成します。
    X軸: 圃場内位置（C3, A3, B2, C1, A1）
    Y軸: 深度（cm）
    Z軸: 圧力値（kPa）

    使用例:
    python manage.py generate_soil_hardness_plot
    python manage.py generate_soil_hardness_plot --output_dir /path/to/output
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--output_dir",
            type=str,
            default=None,
            help="出力ディレクトリ（指定しない場合はカレントディレクトリの 'output' フォルダ）",
        )
        parser.add_argument(
            "--land_ledger_id",
            type=int,
            default=None,
            help="特定の圃場台帳IDのみを対象とする場合に指定",
        )

    def handle(self, *args, **options):
        # 出力ディレクトリの設定
        if options["output_dir"]:
            output_dir = options["output_dir"]
        else:
            # バッチファイルがあるディレクトリにoutputフォルダを作成
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(script_dir, "output")

        os.makedirs(output_dir, exist_ok=True)
        self.stdout.write(f"出力ディレクトリ: {output_dir}")

        # データの状態をチェック
        total_measurements = SoilHardnessMeasurement.objects.count()
        unassigned = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=True
        ).count()
        assigned = total_measurements - unassigned

        self.stdout.write(
            f"土壌硬度測定データ: {assigned}/{total_measurements}件が帳簿割当済み"
        )

        if assigned == 0:
            self.stdout.write(
                self.style.ERROR("❌ 処理中断: 帳簿に紐づけられたデータが存在しません")
            )
            self.stdout.write(
                "💡 解決方法: 先にSoilHardnessMeasurementデータを帳簿に紐づけてください"
            )
            return

        if unassigned > 0:
            self.stdout.write(
                f"⚠️  {unassigned}件の未割当データは除外してプロット作成を続行します"
            )

        # folderごとにプロット作成（重複を排除）
        if options["land_ledger_id"]:
            # 特定の圃場台帳IDが指定されている場合
            folders = (
                SoilHardnessMeasurement.objects.filter(
                    land_ledger_id=options["land_ledger_id"], land_ledger__isnull=False
                )
                .values_list("folder", flat=True)
                .distinct()
            )
        else:
            # 全ての圃場台帳IDを対象とする場合
            folders = (
                SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
                .values_list("folder", flat=True)
                .distinct()
            )

        # Noneやから文字列を除外
        folders = [f for f in folders if f and f.strip()]

        self.stdout.write(f"画像化する圃場数: {len(folders)}")

        plotter = SoilHardnessPlotter(output_dir=output_dir)

        # 処理済みの組み合わせを記録（重複防止）
        processed_combinations = set()

        for folder in folders:
            # 処理済みかチェック
            combination_key = f"{options.get('land_ledger_id', 'all')}_{folder}"
            if combination_key in processed_combinations:
                self.stdout.write(
                    f"⚠️ フォルダ {folder} は既に処理済みのためスキップします"
                )
                continue

            processed_combinations.add(combination_key)
            plotter.plot_3d_surface(
                land_ledger_id=options["land_ledger_id"], folder=folder
            )

        self.stdout.write(self.style.SUCCESS("全てのプロット作成が完了しました"))
