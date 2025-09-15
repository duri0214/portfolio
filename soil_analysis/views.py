import json
import os
import shutil

from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.core.management import call_command
from django.db.models import Prefetch, Count, Min, Max
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    ListView,
    CreateView,
    DetailView,
    TemplateView,
    FormView,
)

from lib.geo.valueobject.coord import GoogleMapsCoord, XarvioCoord
from lib.zipfileservice import ZipFileService
from soil_analysis.domain.repository.company import CompanyRepository
from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)
from soil_analysis.domain.repository.land import LandRepository
from soil_analysis.domain.service.geocode.yahoo import ReverseGeocoderService
from soil_analysis.domain.service.kml import KmlService
from soil_analysis.domain.service.photo_processing import PhotoProcessingService
from soil_analysis.domain.service.reports.reportlayout1 import ReportLayout1
from soil_analysis.domain.valueobject.photo_processing.photo_spot import PhotoSpot
from soil_analysis.forms import CompanyCreateForm, LandCreateForm, UploadForm
from soil_analysis.models import (
    Company,
    Land,
    LandScoreChemical,
    LandReview,
    LandLedger,
    SoilHardnessMeasurementImportErrors,
    SoilHardnessMeasurement,
    SamplingOrder,
    RouteSuggestImport,
    JmaCity,
    JmaRegion,
    JmaPrefecture,
    JmaWeather,
    JmaWarning,
)

SAMPLING_TIMES_PER_BLOCK = 5


class Home(TemplateView):
    template_name = "soil_analysis/home.html"


class CompanyListView(ListView):
    model = Company
    template_name = "soil_analysis/company/list.html"

    def get_queryset(self):
        return super().get_queryset().filter(category__name="農業法人")


class CompanyCreateView(CreateView):
    model = Company
    template_name = "soil_analysis/company/create.html"
    form_class = CompanyCreateForm

    def get_success_url(self):
        return reverse("soil:company_detail", kwargs={"pk": self.object.pk})


class CompanyDetailView(DetailView):
    model = Company
    template_name = "soil_analysis/company/detail.html"


class LandListView(ListView):
    model = Land
    template_name = "soil_analysis/land/list.html"

    def get_queryset(self):
        company_id = self.kwargs["company_id"]
        if not company_id:
            raise Http404("Company ID is required.")

        try:
            company = CompanyRepository.get_company_by_id(company_id)
        except Company.DoesNotExist:
            raise Http404("Company does not exist.")

        weather_prefetch = Prefetch(
            "jma_city__jma_region__jmaweather_set",
            queryset=JmaWeather.objects.all(),
            to_attr="weathers",
        )
        warning_prefetch = Prefetch(
            "jma_city__jma_region__jmawarning_set",
            queryset=JmaWarning.objects.all(),
            to_attr="warnings",
        )
        return (
            super()
            .get_queryset()
            .filter(company=company)
            .prefetch_related(weather_prefetch, warning_prefetch)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_id = self.kwargs["company_id"]
        if not company_id:
            raise Http404("Company ID is required.")

        try:
            company = CompanyRepository.get_company_by_id(company_id)
        except Company.DoesNotExist:
            raise Http404("Company does not exist.")

        context["land_ledger_map"] = LandRepository.get_land_to_ledgers_map(
            context["object_list"]
        )
        context["company"] = company

        return context


class LandCreateView(CreateView):
    model = Land
    template_name = "soil_analysis/land/create.html"
    form_class = LandCreateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["company"] = Company(pk=self.kwargs["company_id"])
        return context

    def form_valid(self, form):
        form.instance.company_id = self.kwargs["company_id"]
        lat, lon = form.instance.latlon.split(", ")
        form.instance.latlon = ",".join([lat, lon])
        return super().form_valid(form)

    def get_success_url(self):
        company = Company(pk=self.kwargs["company_id"])
        return reverse(
            "soil:land_detail", kwargs={"company_id": company.id, "pk": self.object.pk}
        )


class LocationInfoView(View):
    """
    圃場新規作成時のフォームで latlon 入力が終了した際に非同期で情報を取得
    """

    @staticmethod
    def post(request, *args, **kwargs):
        data = json.loads(request.body.decode("utf-8"))
        lat_str, lon_str = data.get("latlon").split(",")
        lat = float(lat_str.strip())
        lon = float(lon_str.strip())

        coord = GoogleMapsCoord(latitude=lat, longitude=lon)
        ydf = ReverseGeocoderService.get_ydf_from_coord(coord)

        try:
            jma_city = ReverseGeocoderService.get_jma_city(ydf)
        except JmaCity.DoesNotExist:
            return JsonResponse(
                {
                    "error": f"{ydf.feature.prefecture.name} {ydf.feature.city.name} が見つかりませんでした"
                }
            )

        return JsonResponse(
            {
                "jma_city_id": jma_city.id,
                "jma_prefecture_id": jma_city.jma_region.jma_prefecture.id,
            }
        )


class PrefecturesView(View):

    @staticmethod
    def get(request):
        prefectures = JmaPrefecture.objects.all()
        data = {"prefectures": list(prefectures.values("id", "name"))}
        return JsonResponse(data)


class PrefectureCitiesView(View):
    """
    圃場新規作成時のフォームで prefecture がonChangeした際に非同期で、該当するcityを取得
    """

    @staticmethod
    def get(request, prefecture_id):
        regions = JmaRegion.objects.filter(jma_prefecture__id=prefecture_id)
        cities = JmaCity.objects.filter(jma_region__in=regions)

        data = {"cities": list(cities.values("id", "name"))}
        return JsonResponse(data)


class LandDetailView(DetailView):
    model = Land
    template_name = "soil_analysis/land/detail.html"


class LandReportChemicalListView(ListView):
    model = LandScoreChemical
    template_name = "soil_analysis/land_report/chemical.html"

    def get_queryset(self):
        land_ledger = LandLedger(self.kwargs["land_ledger_id"])
        return super().get_queryset().filter(land_ledger=land_ledger)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        land_ledger = LandLedger.objects.get(id=self.kwargs["land_ledger_id"])

        context["charts"] = ReportLayout1(land_ledger).publish()
        context["company"] = Company(self.kwargs["company_id"])
        context["land_ledger"] = land_ledger
        context["land_scores"] = LandScoreChemical.objects.filter(
            land_ledger=land_ledger
        )
        context["land_review"] = LandReview.objects.filter(land_ledger=land_ledger)

        return context


class HardnessUploadView(FormView):
    template_name = "soil_analysis/hardness/form.html"
    form_class = UploadForm
    success_url = reverse_lazy("soil:hardness_success")

    def form_valid(self, form):
        # Zipを処理してバッチ実行
        app_name = self.request.resolver_match.app_name
        upload_folder = ZipFileService.handle_uploaded_zip(
            self.request.FILES["file"], app_name
        )
        if os.path.exists(upload_folder):
            call_command("import_soil_hardness", upload_folder)
            try:
                shutil.rmtree(upload_folder)
            except (PermissionError, OSError):
                # ファイル削除エラーは無視して続行
                # OneDriveなどの同期フォルダではこの例外が発生することがある
                pass

        return super().form_valid(form)


class HardnessSuccessView(TemplateView):
    template_name = "soil_analysis/hardness/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["import_errors"] = SoilHardnessMeasurementImportErrors.objects.all()

        # CSVインポートされた硬度測定データをフォルダ名でグループ化し、各フォルダの統計情報を取得
        folder_stats = SoilHardnessMeasurementRepository.get_folder_stats(
            associated_only=False
        )

        context["folder_stats"] = folder_stats
        context["total_records"] = SoilHardnessMeasurement.objects.count()

        return context


class HardnessAssociationView(ListView):
    model = SoilHardnessMeasurement
    template_name = "soil_analysis/hardness/association/list.html"

    def get_queryset(self, **kwargs):
        return SoilHardnessMeasurementRepository.get_folder_groups_for_association()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["land_ledgers"] = LandLedger.objects.all().order_by("pk")

        # 進捗情報を追加
        context["total_groups"] = (
            SoilHardnessMeasurementRepository.get_total_groups_count()
        )
        context["processed_groups"] = (
            SoilHardnessMeasurementRepository.get_processed_groups_count()
        )

        return context

    @staticmethod
    def post(request, **kwargs):
        """
        圃場グループ別処理：
        - 単一圃場グループの帳簿選択処理
        - 処理完了後に次の未処理圃場へ自動遷移
        """

        # 圃場グループ処理ボタンが押された場合（この圃場を処理ボタン）
        if "btn_process_group" in request.POST:
            memory_anchor_str = request.POST.get("btn_process_group")
            try:
                if not memory_anchor_str:
                    messages.error(request, "メモリーアンカーが指定されていません")
                    return HttpResponseRedirect(reverse("soil:hardness_association"))

                memory_anchor = int(memory_anchor_str)
                return HttpResponseRedirect(
                    reverse(
                        "soil:hardness_association_field_group",
                        kwargs={"memory_anchor": memory_anchor},
                    )
                )
            except (ValueError, TypeError) as e:
                # memory_anchor_strが未定義の可能性があるため、エラー変数を使用
                messages.error(
                    request,
                    f"無効なメモリーアンカーです: {memory_anchor_str if 'memory_anchor_str' in locals() else 'unknown'}",
                )
                return HttpResponseRedirect(reverse("soil:hardness_association"))

        return HttpResponseRedirect(reverse("soil:hardness_association"))

    @staticmethod
    def _find_next_unprocessed_group():
        """次の未処理圃場グループのメモリーアンカーを探す"""
        grouped_measurements = SoilHardnessMeasurementRepository.group_measurements()
        for group in grouped_measurements:
            if (
                group.get("measurements")
                and group["measurements"][0].land_ledger is None
            ):
                return group.get("memory_anchor")
        return None


class HardnessAssociationFieldGroupView(ListView):
    """
    単一圃場グループの帳簿選択画面

    TODO: 帳簿マスタ新規登録機能の実装
    - CSVデータ取り込み直後は対応するLandLedgerが存在しないケースが多い
    - このページから直接新規帳簿（LandLedger）を作成できる機能が必要
    - 実装予定機能：
      1. 「新規帳簿作成」ボタンをクリックでモーダル表示
      2. フォルダ名から圃場（Land）を推定して事前選択
      3. 必要項目入力後、新規LandLedgerを作成
      4. 作成完了後、自動的に帳簿選択に反映
    - 関連URL: soil:land_ledger_create_ajax
    - 関連テンプレート: modals/land_ledger_create.html
    """

    model = SoilHardnessMeasurement
    template_name = "soil_analysis/hardness/association/field_group.html"

    def get_queryset(self, **kwargs):
        memory_anchor = self.kwargs.get("memory_anchor")
        # メモリー番号からフォルダを特定し、そのフォルダの全データを取得
        sample_measurement = SoilHardnessMeasurement.objects.filter(
            set_memory=memory_anchor
        ).first()

        if sample_measurement:
            folder_name = sample_measurement.folder
            return SoilHardnessMeasurement.objects.filter(
                folder=folder_name, land_block__isnull=True
            ).order_by("set_memory", "depth")

        return SoilHardnessMeasurement.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        memory_anchor = self.kwargs.get("memory_anchor")

        # 該当圃場グループのフォルダ名から適切な帳簿を絞り込み
        measurements = self.get_queryset()
        folder_name = measurements[0].folder if measurements else ""

        # メモリー番号の範囲を計算
        if measurements:
            memory_numbers = list(
                measurements.values_list("set_memory", flat=True).distinct()
            )
            min_memory = min(memory_numbers)
            max_memory = max(memory_numbers)
        else:
            min_memory = max_memory = memory_anchor

        # フォルダ名に基づいて適切な帳簿のみを表示
        suitable_ledgers = SoilHardnessMeasurementRepository.get_suitable_ledgers(
            folder_name
        )

        context.update(
            {
                "memory_anchor": memory_anchor,
                "min_memory": min_memory,
                "max_memory": max_memory,
                "folder_name": folder_name,
                "land_ledgers": suitable_ledgers,
                "total_groups": SoilHardnessMeasurementRepository.get_total_groups_count(),
                "processed_groups": SoilHardnessMeasurementRepository.get_processed_groups_count(),
            }
        )
        return context

    def post(self, request, **kwargs):
        """圃場グループの帳簿選択処理"""
        form_land_ledger_id = int(request.POST.get("land_ledger"))

        land_ledger = LandLedger.objects.filter(pk=form_land_ledger_id).first()
        if not land_ledger:
            messages.error(request, "指定された帳簿が見つかりません")
            return HttpResponseRedirect(request.path)

        # 処理対象のフォルダのデータを取得（フォルダ単位で処理）
        measurements = self.get_queryset()
        if not measurements:
            messages.error(request, "処理対象のデータが見つかりません")
            return HttpResponseRedirect(reverse("soil:hardness_association"))

        # フォルダ全体のデータを処理対象とする
        hardness_measurements = measurements

        land_block_orders = SamplingOrder.objects.filter(
            sampling_method=land_ledger.sampling_method
        ).order_by("ordering")

        # 1つのland_blockあたりのレコード数を計算（深度×採取回数）
        max_depth = max(m.set_depth for m in hardness_measurements)
        records_per_block = max_depth * SAMPLING_TIMES_PER_BLOCK

        needle = 0
        land_block_count = land_block_orders.count()
        for i, hardness_measurement in enumerate(hardness_measurements):
            if needle < land_block_count:
                hardness_measurement.land_block = land_block_orders[needle].land_block
            hardness_measurement.land_ledger = land_ledger

            # records_per_blockごとにneedleを進める
            if (i + 1) % records_per_block == 0:
                needle += 1

        SoilHardnessMeasurement.objects.bulk_update(
            hardness_measurements, fields=["land_block", "land_ledger"]
        )

        messages.success(
            request,
            f"フォルダ「{measurements[0].folder if measurements else ''}」の処理が完了しました",
        )

        # 処理完了後は常にリスト画面に戻る（シンプル化）
        return HttpResponseRedirect(reverse("soil:hardness_association"))


class HardnessAssociationSuccessView(TemplateView):
    template_name = "soil_analysis/hardness/association/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["import_errors"] = SoilHardnessMeasurementImportErrors.objects.all()

        # 関連付けされたデータのみを対象とする（land_ledgerとland_blockが設定済み）
        associated_measurements = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=False, land_block__isnull=False
        )

        # CSVインポートされた硬度測定データをフォルダ名でグループ化し、各フォルダの統計情報を取得
        folder_stats = SoilHardnessMeasurementRepository.get_folder_stats(
            associated_only=True
        )

        # 各フォルダで使用された機材名とland_block、land_ledger情報を取得
        folder_devices = {}
        folder_blocks = {}
        folder_ledgers = {}

        for measurement in (
            associated_measurements.select_related(
                "set_device", "land_block", "land_ledger__land", "land_ledger__crop"
            )
            .values(
                "folder",
                "set_device__name",
                "land_block__name",
                "land_ledger__land__name",
                "land_ledger__sampling_date",
                "land_ledger__crop__name",
            )
            .distinct()
            .order_by("folder", "land_block__name")  # フォルダとland_block名でソート
        ):
            folder = measurement["folder"]

            # デバイス情報
            device_name = measurement["set_device__name"]
            if folder not in folder_devices:
                folder_devices[folder] = []
            if device_name and device_name not in folder_devices[folder]:
                folder_devices[folder].append(device_name)

            # land_block情報
            block_name = measurement["land_block__name"]
            if folder not in folder_blocks:
                folder_blocks[folder] = []
            if block_name and block_name not in folder_blocks[folder]:
                folder_blocks[folder].append(block_name)

        # 各フォルダのland_block名をソート
        for folder in folder_blocks:
            folder_blocks[folder].sort()

        # land_ledger情報を収集
        for measurement in (
            associated_measurements.select_related(
                "set_device", "land_block", "land_ledger__land", "land_ledger__crop"
            )
            .values(
                "folder",
                "land_ledger__land__name",
                "land_ledger__sampling_date",
                "land_ledger__crop__name",
            )
            .distinct()
        ):
            folder = measurement["folder"]
            if folder not in folder_ledgers:
                folder_ledgers[folder] = []
            ledger_info = {
                "land_name": measurement["land_ledger__land__name"],
                "sampling_date": measurement["land_ledger__sampling_date"],
                "crop_name": measurement["land_ledger__crop__name"],
            }
            if ledger_info not in folder_ledgers[folder]:
                folder_ledgers[folder].append(ledger_info)

        # folder_statsに関連付け情報を追加
        folder_stats_with_details = []
        for stats in folder_stats:
            stats["device_names"] = folder_devices.get(stats["folder"], [])
            stats["land_block_names"] = folder_blocks.get(stats["folder"], [])
            stats["land_ledger_info"] = folder_ledgers.get(stats["folder"], [])
            folder_stats_with_details.append(stats)

        # Land Block別集計
        land_block_stats = (
            associated_measurements.select_related("land_block")
            .values("land_block__name")
            .annotate(
                count=Count("id"),
                set_depth=Min("set_depth"),  # 設定深度を表示（通常は固定値60cm）
                min_pressure=Min("pressure"),
                max_pressure=Max("pressure"),
            )
            .order_by("land_block__name")
        )

        # Land Ledger別集計
        land_ledger_stats = (
            associated_measurements.select_related(
                "land_ledger__land", "land_ledger__crop", "land_ledger__land_period"
            )
            .values(
                "land_ledger__land__name",
                "land_ledger__sampling_date",
                "land_ledger__crop__name",
                "land_ledger__land_period__name",
            )
            .annotate(
                count=Count("id"),
            )
            .order_by("land_ledger__sampling_date")
        )

        # レスポンス用にフィールド名を整理
        land_block_stats_formatted = []
        for stat in land_block_stats:
            land_block_stats_formatted.append(
                {
                    "land_block_name": stat["land_block__name"],
                    "count": stat["count"],
                    "set_depth": stat["set_depth"],
                    "min_pressure": stat["min_pressure"],
                    "max_pressure": stat["max_pressure"],
                }
            )

        land_ledger_stats_formatted = []
        for stat in land_ledger_stats:
            land_ledger_stats_formatted.append(
                {
                    "land_name": stat["land_ledger__land__name"],
                    "sampling_date": stat["land_ledger__sampling_date"],
                    "crop_name": stat["land_ledger__crop__name"],
                    "period_name": stat["land_ledger__land_period__name"],
                    "count": stat["count"],
                }
            )

        context["folder_stats"] = folder_stats_with_details
        context["land_block_stats"] = land_block_stats_formatted
        context["land_ledger_stats"] = land_ledger_stats_formatted
        context["total_records"] = associated_measurements.count()

        return context


class RouteSuggestUploadView(FormView):
    template_name = "soil_analysis/route_suggest/form.html"
    form_class = UploadForm
    success_url = reverse_lazy("soil:route_suggest_ordering")

    def form_valid(self, form):
        """
        Notes: Directions API の地点を制限する
         可能であれば、クエリでのユーザー入力を最大 10 地点に制限します。10 を超える地点を含むリクエストは、課金レートが高くなります。
         https://developers.google.com/maps/optimization-guide?hl=ja#routes
        """
        upload_file: UploadedFile = self.request.FILES["file"]
        kml_raw = upload_file.read().decode("utf-8")
        kml_service = KmlService()
        land_location_list = kml_service.parse_kml(kml_raw)

        if len(land_location_list) < 2:
            messages.error(self.request, "少なくとも 2 つの場所を指定してください")
            return redirect(self.request.META.get("HTTP_REFERER"))

        if len(land_location_list) > 10:
            messages.error(
                self.request,
                "GoogleMapsAPIのレート上昇制約により 10 地点までしか計算できません",
            )
            return redirect(self.request.META.get("HTTP_REFERER"))

        entities = []
        for land_location in land_location_list:
            coordinates_str = land_location.center.to_google().to_str()
            entity = RouteSuggestImport.objects.create(
                name=land_location.name, coord=coordinates_str
            )
            entities.append(entity)
        RouteSuggestImport.objects.all().delete()
        RouteSuggestImport.objects.bulk_create(entities)

        return super().form_valid(form)


class RouteSuggestOrderingView(ListView):
    model = RouteSuggestImport
    template_name = "soil_analysis/route_suggest/ordering.html"

    def post(self, request, *args, **kwargs):
        order_data = self.request.POST.get("order_data")

        try:
            if order_data:
                order_ids = order_data.split(",")
                for order, order_id in enumerate(order_ids, start=1):
                    route_suggest = RouteSuggestImport.objects.get(pk=order_id)
                    route_suggest.ordering = order
                    route_suggest.save()

            messages.success(request, "Data updated successfully")
            return redirect(reverse_lazy("soil:route_suggest_success"))

        except RouteSuggestImport.DoesNotExist:
            messages.error(request, "Invalid order data provided.")
            return redirect(request.META.get("HTTP_REFERER"))


class RouteSuggestSuccessView(TemplateView):
    template_name = "soil_analysis/route_suggest/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route_suggest_imports = RouteSuggestImport.objects.all().order_by("ordering")
        company_list = []
        land_list = []
        for route_suggest_import in route_suggest_imports:
            company_name, land_name = route_suggest_import.name.split(" - ")
            company_list.append(company_name)
            land_list.append({"name": land_name, "coord": route_suggest_import.coord})

        context["company_list"] = company_list
        context["land_list"] = land_list
        context["coord_list"] = list(land["coord"] for land in land_list)
        context["google_maps_fe_api_key"] = os.getenv("GOOGLE_MAPS_FE_API_KEY")

        return context


class AssociatePictureAndLandView(ListView):
    model = Land
    template_name = "soil_analysis/picture_land_associate/form.html"
    context_object_name = "land_list"
    success_url = reverse_lazy("soil:associate_picture_and_land_result")

    def get_queryset(self):
        return Land.objects.all().order_by("pk")

    @staticmethod
    def get_dummy_photo_spots() -> list[XarvioCoord]:
        """
        テスト用の撮影位置データを返します
        注: GPSが正確な撮影位置を取得できるようになったらここを置き換える
        """
        return [
            XarvioCoord(longitude=137.64905, latitude=34.74424),  # 静岡ススムA1用
            XarvioCoord(longitude=137.64921, latitude=34.744),  # 静岡ススムA2用
            XarvioCoord(longitude=137.64938, latitude=34.74374),  # 静岡ススムA3用
            XarvioCoord(longitude=137.6496, latitude=34.7434),  # 静岡ススムA4用
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photo_spots"] = self.get_dummy_photo_spots()
        return context

    def post(self, request, *args, **kwargs):
        if "photo_spot" not in request.POST:
            return self.render_to_response(self.get_context_data())

        spot_index = int(request.POST["photo_spot"])
        photo_spots = self.get_dummy_photo_spots()

        photo_spot = PhotoSpot(photo_spots[spot_index])

        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, list(self.get_queryset()))

        # セッションに結果を保存
        self.request.session["nearest_land_id"] = nearest_land.id
        self.request.session["photo_spot_coord"] = (
            photo_spot.original_position.to_google().to_str()
        )

        return HttpResponseRedirect(self.success_url)


class AssociatePictureAndLandResultView(TemplateView):
    template_name = "soil_analysis/picture_land_associate/result.html"

    # Googleマップルートのパラメータを定数として定義
    GOOGLE_MAPS_PARAMS = {
        "DISPLAY_OPTIONS": "!3m1!4b1",  # マップの表示オプション
        "ROUTE_PARAMS": "!4m2!4m1",  # ルート関連パラメータ
        "TRANSPORT_MODES": {
            "CAR": "!3e0",  # 自動車での移動
            "PUBLIC_TRANSPORT": "!3e1",  # 公共交通機関での移動
            "WALKING": "!3e2",  # 徒歩での移動
            "BICYCLE": "!3e3",  # 自転車での移動
        },
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        photo_spot_coord = self.request.session.get("photo_spot_coord")
        nearest_land_id = self.request.session.get("nearest_land_id")

        if nearest_land_id and photo_spot_coord:
            # 圃場idから圃場データを取得
            land = LandRepository.find_land_by_id(nearest_land_id)

            # ルートURL作成（徒歩ルート指定）
            context["route_url"] = (
                f"https://www.google.com/maps/dir/{photo_spot_coord}/{land.to_google().to_str()}/"
                f"data={self.GOOGLE_MAPS_PARAMS['DISPLAY_OPTIONS']}"
                f"{self.GOOGLE_MAPS_PARAMS['ROUTE_PARAMS']}"
                f"{self.GOOGLE_MAPS_PARAMS['TRANSPORT_MODES']['WALKING']}"
            )

            context["nearest_land"] = {
                "name": land.name,
                "location": land.to_google().to_str(),
                "area": land.area,
                "owner": land.owner.username,
            }
            context["photo_spot_coord"] = photo_spot_coord

        return context
