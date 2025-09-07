import os

import matplotlib.pyplot as plt
import numpy as np

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
        # ファイル名の作成
        filename = (
            f"soil_hardness_{company_name}_{land_name}_{sampling_date}_{plot_type}.png"
        )
        # ファイル名から無効な文字を除去
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        save_path = os.path.join(self.output_dir, filename)

        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        print(f"保存完了: {save_path}")
        return save_path

    def plot_row_subplots(self, land_ledger_id=None):
        """土壌硬度データを行ごとのサブプロットとして描画

        各行（A, B, C）ごとに1つのサブプロットを作成し、
        X軸に位置（1, 2, 3）、Y軸に深度、色で圧力値を表現

        Args:
            land_ledger_id: 特定の圃場台帳ID（Noneの場合は全データ）
        """
        # データ取得
        data = self._get_measurement_data(land_ledger_id)
        queryset = data["queryset"]
        land_ledgers = data["land_ledgers"]

        for ledger_id in land_ledgers:
            ledger_data = queryset.filter(land_ledger_id=ledger_id)

            # 圃場情報取得
            land_info = self._get_land_info(ledger_data)
            if land_info is None:
                continue

            company_name, land_name, sampling_date = land_info

            # 3つの行（A, B, C）に対応する3つのサブプロット作成
            fig, axes = plt.subplots(3, 1, figsize=(10, 15))
            fig.suptitle(
                f"{company_name} - {land_name} 土壌圧力分布 ({sampling_date})",
                fontsize=16,
            )

            # 行の名前
            row_names = ["A", "B", "C"]

            # 各行のデータをプロット
            for i, row_name in enumerate(row_names):
                ax = axes[i]

                # この行のデータのみフィルタリング
                row_data = ledger_data.filter(land_block__name__startswith=row_name)

                if not row_data.exists():
                    ax.set_title(f"行 {row_name}: データなし", fontsize=14)
                    continue

                # X軸の値：位置番号（1, 2, 3）
                x_positions = [1, 2, 3]
                x_labels = [f"{row_name}1", f"{row_name}2", f"{row_name}3"]

                # 深度の範囲
                depths = sorted(row_data.values_list("depth", flat=True).distinct())

                # 各位置でのデータをカラーマップとして表示
                pressure_matrix = np.zeros((len(depths), len(x_positions)))
                pressure_matrix.fill(np.nan)  # 欠損値をNaNで初期化

                # 圧力データを行列に格納
                for pos_idx, pos_num in enumerate([1, 2, 3]):
                    pos_data = row_data.filter(set_memory=pos_num).order_by("depth")

                    for data in pos_data:
                        depth_idx = depths.index(data.depth)
                        pressure_matrix[depth_idx, pos_idx] = data.pressure

                # ヒートマップとして表示
                # extent=(left, right, bottom, top)
                extent = (0.5, 3.5, float(max(depths)), float(min(depths)))
                im = ax.imshow(
                    pressure_matrix,
                    cmap="viridis",
                    aspect="auto",
                    interpolation="nearest",
                    extent=extent,
                )

                # カラーバー
                cbar = fig.colorbar(im, ax=ax)
                cbar.set_label("圧力 (kPa)")

                # 軸ラベル
                ax.set_title(f"行 {row_name}", fontsize=14)
                ax.set_xticks(x_positions)
                ax.set_xticklabels(x_labels)
                ax.set_ylabel("深度 (cm)")
                ax.set_xlabel("圃場内位置")
                ax.grid(True, alpha=0.3)

            # レイアウト調整
            plt.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))  # タイトル用にスペースを確保

            # 保存
            self._save_plot(fig, company_name, land_name, sampling_date, "row_plot")

    def plot_3d_view(self, land_ledger_id=None, depth=15):
        """特定深度での3D表示

        Args:
            land_ledger_id: 特定の圃場台帳ID（Noneの場合は全データ）
            depth: 表示する深度（cm）
        """
        # データ取得
        data = self._get_measurement_data(land_ledger_id)
        # 指定された深度でフィルタリング
        queryset = data["queryset"].filter(depth=depth)
        land_ledgers = queryset.values_list("land_ledger", flat=True).distinct()

        for ledger_id in land_ledgers:
            ledger_data = queryset.filter(land_ledger_id=ledger_id)

            # 圃場情報取得
            land_info = self._get_land_info(ledger_data)
            if land_info is None:
                continue

            company_name, land_name, sampling_date = land_info

            # 3Dプロット作成
            fig = plt.figure(figsize=(10, 8))
            # 3D軸メソッドを使用するための明示的なインポート

            ax = fig.add_subplot(111, projection="3d")

            # 行と列の名前
            rows = ["A", "B", "C"]
            cols = ["1", "2", "3"]  # 文字列に変更
            col_nums = [1, 2, 3]  # 数値版

            # X, Y座標メッシュを作成
            x_range = np.arange(len(cols))
            y_range = np.arange(len(rows))
            x_mesh, y_mesh = np.meshgrid(x_range, y_range)

            # Z値（圧力）の初期化
            z_data = np.zeros((len(rows), len(cols)))
            z_data.fill(np.nan)  # 欠損値をNaNで初期化

            # データをZ行列に格納
            for data_point in ledger_data:
                block_name = data_point.land_block.name[0]  # 最初の文字（A, B, C）
                position = data_point.set_memory  # 位置番号（1, 2, 3）

                if block_name in rows and position in col_nums:
                    row_idx = rows.index(block_name)
                    col_idx = col_nums.index(position)
                    z_data[row_idx, col_idx] = data_point.pressure

            # 欠損値を補間
            masked_z = np.ma.masked_invalid(z_data)
            x_valid, y_valid = np.meshgrid(x_range, y_range)
            x_valid = x_valid[~masked_z.mask]
            y_valid = y_valid[~masked_z.mask]
            z_valid = masked_z.compressed()

            # 3D表面プロット
            if len(z_valid) > 3:  # 最低3点必要
                # plot_surfaceを使用して3D表面プロットを描画
                surf = ax.plot_surface(
                    x_mesh, y_mesh, z_data, cmap="viridis", edgecolor="none", alpha=0.8
                )

                # カラーバー
                fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label="圧力 (kPa)")
            else:
                # データが少ない場合は散布図として表示
                ax.scatter(
                    x_valid,
                    y_valid,
                    z_valid,
                    c=z_valid,
                    cmap="viridis",
                    s=100,
                    marker="o",
                )

            # 軸ラベル
            ax.set_xlabel("圃場内位置（列）")
            ax.set_ylabel("圃場内位置（行）")
            ax.set_zlabel("圧力 (kPa)")

            # 軸目盛りのカスタマイズ
            ax.set_xticks(x_range)
            ax.set_yticks(y_range)
            ax.set_xticklabels(cols)
            ax.set_yticklabels(rows)

            ax.set_title(
                f"{company_name} - {land_name}\n土壌圧力分布 (深度: {depth}cm)"
            )

            # 保存
            plot_type = f"depth{depth}cm_3d"
            self._save_plot(fig, company_name, land_name, sampling_date, plot_type)


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

    # 行ごとのサブプロット
    plotter.plot_row_subplots(land_ledger_id=land_ledger_id)

    # 代表的な深度での3D表示
    for depth in [5, 15, 30]:
        plotter.plot_3d_view(land_ledger_id=land_ledger_id, depth=depth)


if __name__ == "__main__":
    # カレントディレクトリに output フォルダを作成して使用
    plot_output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(plot_output_dir, exist_ok=True)
    print(f"出力ディレクトリ: {plot_output_dir}")

    # Case1: 全データから作成
    create_soil_hardness_plots(output_dir=plot_output_dir)

    # Case2: 特定の圃場台帳IDを指定する場合
    # create_soil_hardness_plots(land_ledger_id=1, output_dir=plot_output_dir)
