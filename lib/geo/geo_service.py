import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Rectangle
from rasterio.windows import Window

from lib.geo.valueobject.coords import (
    MetaData,
    GoogleMapCoords,
    RectangleCoords,
    Point,
)


class GeoService:
    @staticmethod
    def read_metadata(file_path: str) -> MetaData:
        """
        指定したGeoTIFFファイルを読み込み、メタデータをMetaDataオブジェクトに変換する。

        Args:
            file_path (str): GeoTIFFファイルのパス。

        Returns:
            MetaData: メタデータを格納したオブジェクト。
        """
        with rasterio.open(file_path) as dataset:
            meta = dataset.meta
            return MetaData(
                driver=meta["driver"],
                dtype=meta["dtype"],
                nodata=meta["nodata"],
                width=meta["width"],
                height=meta["height"],
                count=meta["count"],
                crs=meta["crs"],
                transform=meta["transform"],
            )

    @staticmethod
    def get_center_coordinates(file_path: str) -> GoogleMapCoords:
        """
        指定したGeoTIFFファイルの中央ピクセルの緯度経度を取得する。

        Args:
            file_path (str): GeoTIFFファイルのパス。

        Returns:
            tuple[float, float]: 中央ピクセルの緯度と経度。
        """
        with rasterio.open(file_path) as dataset:
            width, height = dataset.width, dataset.height
            transform = dataset.transform

            # 中央ピクセルの行列インデックス
            center_x = width // 2
            center_y = height // 2

            # ピクセル座標を地理座標に変換
            lon, lat = rasterio.transform.xy(
                transform, center_y, center_x, offset="center"
            )
            return GoogleMapCoords(latitude=lat, longitude=lon)

    @staticmethod
    def get_pixel_coordinates_from_geo(
        file_path: str, coords: GoogleMapCoords
    ) -> tuple[int, int]:
        """
        緯度経度からピクセル座標に変換する。

        Args:
            file_path (str): GeoTIFFファイルのパス。
            coords (GoogleMapCoords): 緯度経度のデータ。

        Returns:
            tuple[int, int]: ピクセル座標 (x, y)。
        """
        with rasterio.open(file_path) as dataset:
            transform = dataset.transform

            # 緯度経度をピクセル座標に変換
            col, row = ~transform * (coords.longitude, coords.latitude)  # 逆変換

            return int(col), int(row)

    @staticmethod
    def get_pixel_coordinates(
        file_path: str, pixel_x: int, pixel_y: int
    ) -> GoogleMapCoords:
        """
        指定したピクセルの座標（緯度経度）を取得する。

        Args:
            file_path (str): GeoTIFFファイルのパス。
            pixel_x (int): X座標（横位置）のピクセル位置。
            pixel_y (int): Y座標（縦位置）のピクセル位置。

        Returns:
            tuple[float, float]: 指定したピクセル位置の緯度経度。
        """
        with rasterio.open(file_path) as dataset:
            transform = dataset.transform

            # ピクセル座標を地理座標に変換
            lon, lat = rasterio.transform.xy(
                transform, pixel_y, pixel_x, offset="center"
            )
            return GoogleMapCoords(latitude=lat, longitude=lon)

    @staticmethod
    def read_band_as_array(file_path: str, band_index: int = 1) -> np.ndarray:
        """
        GeoTIFF ファイルの指定されたバンドを numpy 配列として読み込む。

        Args:
            file_path (str): GeoTIFFファイルのパス。
            band_index (int): 読み込むバンドのインデックス（デフォルトは1）。

        Returns:
            np.ndarray: 指定バンドのデータ。
        """
        with rasterio.open(file_path) as dataset:
            return dataset.read(band_index)

    @staticmethod
    def get_value_by_coords(file_path: str, coords: GoogleMapCoords) -> float:
        """
        緯度経度を指定してピンポイントの値を取得する。

        Args:
            file_path (str): GeoTIFFファイルのパス。
            coords (GoogleMapCoords): 緯度経度。

        Returns:
            float: 指定した位置の値。
        """
        with rasterio.open(file_path) as dataset:
            py, px = dataset.index(coords.longitude, coords.latitude)
            return dataset.read(1)[py, px]

    @staticmethod
    def crop_by_bbox(
        file_path: str, min_coords: GoogleMapCoords, max_coords: GoogleMapCoords
    ) -> np.ndarray:
        """
        指定した緯度経度範囲のデータを切り取る。

        Args:
            file_path (str): GeoTIFFファイルのパス。
            min_coords (GoogleMapCoords): 左下の緯度経度。
            max_coords (GoogleMapCoords): 右上の緯度経度。

        Returns:
            np.ndarray: 指定範囲のデータ。
        """
        with rasterio.open(file_path) as src:
            py, px = src.index(min_coords.longitude, min_coords.latitude)
            py2, px2 = src.index(max_coords.longitude, max_coords.latitude)

            # 左上 (y: py2), 右下 (y: py) のピクセル範囲を指定
            window = Window.from_slices((py2, py + 1), (px, px2 + 1))
            return src.read(1, window=window)

    @staticmethod
    def draw_bbox_on_cropped_image(
        full_image_data: np.ndarray,
        rectangle_coords: RectangleCoords,
        output_path: str,
    ):
        """
        全体画像に赤枠を描画し、保存する関数

        Args:
            full_image_data (np.ndarray): 元の全体画像データ
            rectangle_coords (RectangleCoords): 赤枠を描く矩形の座標範囲
            output_path (str): 保存先の画像パス
        """
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.imshow(full_image_data, cmap="gray")  # グレースケール画像の表示

        # 赤枠を描画する
        rect = Rectangle(
            (rectangle_coords.min_point.x, rectangle_coords.min_point.y),  # 左下の座標
            rectangle_coords.width,  # 幅
            rectangle_coords.height,  # 高さ
            linewidth=2,
            edgecolor="red",
            facecolor="none",
        )
        ax.add_patch(rect)

        # 軸を非表示
        ax.axis("off")

        # 画像を保存
        plt.savefig(output_path, bbox_inches="tight", pad_inches=0)
        plt.close()

        print(f"Image with bounding box saved to: {output_path}")

    @staticmethod
    def calculate_forest_percentage_from_array(
        data_array: np.ndarray, forest_threshold: float
    ) -> float:
        """
        ndarray 形式のデータから森が占める割合を計算する。

        Args:
            data_array (np.ndarray): 切り出されたデータの配列。
            forest_threshold (float): 森と判定するピクセル値の閾値。

        Returns:
            float: 森が占める割合（0～1）。
        """
        # 森と判定されるピクセル数を計算
        forest_pixels = np.sum(data_array > forest_threshold)
        total_pixels = data_array.size

        return forest_pixels / total_pixels if total_pixels > 0 else 0

    @staticmethod
    def rescale_cropped_data_and_save(cropped_data: np.ndarray, output_path: str):
        """
        切り取ったデータをリスケールし、保存する。

        Args:
            cropped_data (np.ndarray): 切り取った画像データ。
            output_path (str): 保存先の画像パス。
        """

        def rescale_data(data: np.ndarray) -> np.ndarray:
            data_min, data_max = np.percentile(data, [2, 98])
            rescaled = (data - data_min) / (data_max - data_min) * 255
            rescaled = np.clip(rescaled, 0, 255)
            return rescaled.astype(np.uint8)

        rescaled_data = rescale_data(cropped_data)
        plt.imshow(rescaled_data, cmap="gray")
        plt.axis("off")
        plt.savefig(output_path, bbox_inches="tight", pad_inches=0)
        plt.close()
        print(f"Rescaled cropped image saved to: {output_path}")


# サンプル利用(tifは800MBとかあるのでgithubにアップロードはできない）
if __name__ == "__main__":
    target_file_path = r"C:\Users\yoshi\Downloads\衛星画像\sample_geo_picture.tif"

    geo_service = GeoService()

    # メタデータを取得して表示
    metadata_vo = geo_service.read_metadata(target_file_path)
    print("Metadata:", metadata_vo)

    # 画像の中央ピクセルの緯度経度を取得して表示
    center_coords = geo_service.get_center_coordinates(target_file_path)
    print(f"GoogleMap format(Center): {center_coords.to_str()}")

    # 任意のピクセル位置(例えばピクセル位置 (100, 150)) の緯度経度を取得して表示
    pixel_coords = geo_service.get_pixel_coordinates(target_file_path, 100, 150)
    print(f"GoogleMap format(Specific (100, 150)): {pixel_coords.to_str()}")

    # 指定されたバンドを numpy 配列として読み込んで表示
    band_array = geo_service.read_band_as_array(target_file_path, band_index=1)
    print("Band Array Shape:", band_array.shape)

    # 緯度経度を指定してピクセル値を取得して表示
    target_coords = GoogleMapCoords(
        latitude=37.391049, longitude=136.902589
    )  # 任意の緯度経度
    value = geo_service.get_value_by_coords(target_file_path, target_coords)
    print(f"Value at ({target_coords.latitude}, {target_coords.longitude}): {value}")

    # 緯度経度範囲を指定して画像を切り取る
    location_coords = {
        "schoolyard": [
            GoogleMapCoords(latitude=37.389831, longitude=136.902589),  # 左下（西南）
            GoogleMapCoords(latitude=37.391049, longitude=136.904030),  # 右上（北東）
        ],
        "forest": [
            GoogleMapCoords(latitude=37.388843, longitude=136.903071),  # 左下（西南）
            GoogleMapCoords(latitude=37.389491, longitude=136.904273),  # 右上（北東）
        ],
    }

    location = "schoolyard"
    w_cropped_data = geo_service.crop_by_bbox(
        file_path=target_file_path,
        min_coords=location_coords[location][0],
        max_coords=location_coords[location][1],
    )
    print("Cropped Data Shape:", w_cropped_data.shape)

    forest_percentage = geo_service.calculate_forest_percentage_from_array(
        data_array=w_cropped_data,
        forest_threshold=128,  # 森の閾値（例）
    )
    print(f"Forest Percentage: {forest_percentage * 100:.2f}%")

    # リスケールして保存（拡大写真用）
    cropped_rescaled_path = "image_with_bbox_cropped.png"
    geo_service.rescale_cropped_data_and_save(w_cropped_data, cropped_rescaled_path)

    # 緯度経度範囲からピクセル位置を計算
    min_pixel_coords = geo_service.get_pixel_coordinates_from_geo(
        target_file_path, location_coords[location][0]
    )
    max_pixel_coords = geo_service.get_pixel_coordinates_from_geo(
        target_file_path, location_coords[location][1]
    )

    # 全体写真に赤枠を描画して保存
    output_image_path = "image_with_bbox_full.png"
    geo_service.draw_bbox_on_cropped_image(
        full_image_data=geo_service.read_band_as_array(target_file_path),
        rectangle_coords=RectangleCoords(
            min_point=Point(*min_pixel_coords),  # 左下（西南）
            max_point=Point(*max_pixel_coords),  # 右上（北東）
        ),
        output_path=output_image_path,
    )

    print("Images with bounding boxes have been saved.")
