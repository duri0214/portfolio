import os

import matplotlib.pyplot as plt
import numpy as np


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

        print(f"保存完了: {save_path}")
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

        land_ledgers = queryset.values_list("land_ledger", flat=True).distinct()

        for ledger_id in land_ledgers:
            ledger_data = queryset.filter(land_ledger_id=ledger_id)

            # 同じfolderのデータのみを取得
            if folder:
                ledger_data = ledger_data.filter(folder=folder)

            # 圃場情報取得
            land_info = self._get_land_info(ledger_data)
            if land_info is None:
                continue

            company_name, land_name, sampling_date = land_info

            # folderが指定されている場合はタイトルに追加
            if folder:
                land_name = f"{land_name}_{folder}"

            # 圃場内位置の組み合わせを取得（A1, A2, A3, B1, B2, B3, C1, C2, C3）
            location_combinations = []
            for data_point in ledger_data:
                block_name = data_point.land_block.name[0]  # A, B, C
                position = data_point.set_memory  # 1, 2, 3
                combination = f"{block_name}{position}"
                if combination not in location_combinations:
                    location_combinations.append(combination)

            location_combinations.sort()  # ソート

            # 深度のリストを取得
            depths = sorted(ledger_data.values_list("depth", flat=True).distinct())

            # 圧力データを2次元配列に格納（locations x depths）
            pressure_data = np.zeros((len(location_combinations), len(depths)))
            pressure_data.fill(np.nan)

            for data_point in ledger_data:
                block_name = data_point.land_block.name[0]
                position = data_point.set_memory
                combination = f"{block_name}{position}"

                try:
                    location_idx = location_combinations.index(combination)
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

            # 保存
            self._save_plot(fig, company_name, land_name, sampling_date, "3d_surface")


def create_soil_hardness_plots(land_ledger_id=None, output_dir="."):
    """土壌硬度プロットの作成

    Args:
        land_ledger_id: 特定の圃場台帳ID（Noneの場合は全データ）
        output_dir: 出力ディレクトリ（デフォルトはカレントディレクトリ）
    """
    # データの状態をチェック
    total_measurements = SoilHardnessMeasurement.objects.count()
    unassigned = SoilHardnessMeasurement.objects.filter(
        land_ledger__isnull=True
    ).count()
    assigned = total_measurements - unassigned

    print(f"土壌硬度測定データ: {assigned}/{total_measurements}件が帳簿割当済み")

    if assigned == 0:
        print("❌ 処理中断: 帳簿に紐づけられたデータが存在しません")
        print("💡 解決方法: 先にSoilHardnessMeasurementデータを帳簿に紐づけてください")
        return

    if unassigned > 0:
        print(f"⚠️  {unassigned}件の未割当データは除外してプロット作成を続行します")

    plotter = SoilHardnessPlotter(output_dir=output_dir)

    # 統合された3D表面プロット
    plotter.plot_3d_surface(land_ledger_id=land_ledger_id)


if __name__ == "__main__":
    # カレントディレクトリに output フォルダを作成して使用
    plot_output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(plot_output_dir, exist_ok=True)
    print(f"出力ディレクトリ: {plot_output_dir}")

    # folderごとにプロット作成
    from soil_analysis.models import SoilHardnessMeasurement

    folders = SoilHardnessMeasurement.objects.values_list(
        "folder", flat=True
    ).distinct()

    print(f"検出されたフォルダ数: {len(folders)}")

    plotter = SoilHardnessPlotter(output_dir=plot_output_dir)

    for folder in folders:
        if folder:  # 空のfolderをスキップ
            print(f"フォルダ {folder} のプロット作成中...")
            plotter.plot_3d_surface(folder=folder)

    print("全てのプロット作成が完了しました")
