import json
import os
import shutil

from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.core.management import call_command
from django.db.models import Prefetch
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
    LandBlock,
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
        return context


class HardnessAssociationView(ListView):
    model = SoilHardnessMeasurement
    template_name = "soil_analysis/hardness/association/list.html"

    def get_queryset(self, **kwargs):
        return SoilHardnessMeasurementRepository.group_measurements()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["land_ledgers"] = LandLedger.objects.all().order_by("pk")
        return context

    @staticmethod
    def post(request, **kwargs):
        """
        R型 で登録するときは、圃場の1ブロックが5点計測なので、採土法（5点法、9点法）の回数を乗ずると、1圃場での採取回数になる
        R型以外のときはIndividualViewへ飛ぶ
        """
        form_land_ledger_id = int(request.POST.get("land_ledger")[0])
        if "btn_individual" in request.POST:
            return HttpResponseRedirect(
                reverse(
                    "soil:hardness_association_individual",
                    kwargs={
                        "memory_anchor": int(request.POST.get("btn_individual")),
                        "land_ledger": form_land_ledger_id,
                    },
                )
            )

        form_checkboxes = [
            int(checkbox) for checkbox in request.POST.getlist("form_checkboxes[]")
        ]
        if form_checkboxes:
            land_ledger = LandLedger.objects.filter(pk=form_land_ledger_id).first()

            blocks = SamplingOrder.objects.filter(
                sampling_method=land_ledger.sampling_method
            ).count()
            total_sampling_times = blocks * SAMPLING_TIMES_PER_BLOCK

            land_block_orders = SamplingOrder.objects.filter(
                sampling_method=land_ledger.sampling_method
            ).order_by("ordering")
            for memory_anchor in form_checkboxes:
                hardness_measurements = (
                    SoilHardnessMeasurementRepository.get_measurements_by_memory_range(
                        memory_anchor, total_sampling_times
                    )
                )

                needle = 0
                max_needle = land_block_orders.count() - 1  # 最大インデックスを取得
                for i, hardness_measurement in enumerate(hardness_measurements):
                    # 硬度測定データ (hardness_measurements) に対して、
                    # 適切な土地ブロック情報 (land_block) と土地台帳 (land_ledger) を割り当て
                    if needle <= max_needle:  # 境界チェック
                        hardness_measurement.land_block = land_block_orders[
                            needle
                        ].land_block
                    hardness_measurement.land_ledger = land_ledger

                    records_per_block = (
                        hardness_measurement.set_depth * SAMPLING_TIMES_PER_BLOCK
                    )
                    can_forward_the_needle = i > 0 and i % records_per_block == 0
                    if (
                        can_forward_the_needle and needle < max_needle
                    ):  # needleが範囲内の場合のみインクリメント
                        needle += 1

                SoilHardnessMeasurement.objects.bulk_update(
                    hardness_measurements, fields=["land_block", "land_ledger"]
                )

        return HttpResponseRedirect(reverse("soil:hardness_association_success"))


class HardnessAssociationIndividualView(ListView):
    model = SoilHardnessMeasurement
    template_name = "soil_analysis/hardness/association/individual/list.html"

    def get_queryset(self, **kwargs):
        form_memory_anchor = self.kwargs.get("memory_anchor")
        form_land_ledger_id = int(self.kwargs.get("land_ledger"))

        land_ledger = LandLedger.objects.filter(pk=form_land_ledger_id).first()

        blocks = SamplingOrder.objects.filter(
            sampling_method=land_ledger.sampling_method
        ).count()
        total_sampling_times = blocks * SAMPLING_TIMES_PER_BLOCK

        hardness_measurements = (
            SoilHardnessMeasurementRepository.get_measurements_by_memory_range(
                form_memory_anchor, total_sampling_times
            )
        )

        return SoilHardnessMeasurementRepository.group_measurements(
            hardness_measurements
        )

    def get_context_data(self, **kwargs):
        form_memory_anchor = self.kwargs.get("memory_anchor")
        form_land_ledger_id = int(self.kwargs.get("land_ledger"))
        context = super().get_context_data(**kwargs)
        context["memory_anchor"] = form_memory_anchor
        context["land_ledger"] = form_land_ledger_id
        context["land_blocks"] = LandBlock.objects.order_by("pk").all()
        return context

    def post(self, request, **kwargs):
        """
        R型 以外で登録したいとき
        フォームから25レコードの情報がくるのでそれぞれを更新する
        """
        form_memory_anchor = self.kwargs.get("memory_anchor")
        form_land_ledger_id = int(self.kwargs.get("land_ledger"))
        form_land_blocks = request.POST.getlist("land-blocks[]")

        land_ledger = LandLedger.objects.filter(pk=form_land_ledger_id).first()

        blocks = SamplingOrder.objects.filter(
            sampling_method=land_ledger.sampling_method
        ).count()
        total_sampling_times = blocks * SAMPLING_TIMES_PER_BLOCK

        hardness_measurements = (
            SoilHardnessMeasurementRepository.get_measurements_by_memory_range(
                form_memory_anchor, total_sampling_times
            )
        )

        for i, hardness_measurement in enumerate(hardness_measurements):
            needle = i // 60
            hardness_measurement.land_block_id = form_land_blocks[needle]
            hardness_measurement.land_ledger = land_ledger
        SoilHardnessMeasurement.objects.bulk_update(
            hardness_measurements, fields=["land_block", "land_ledger"]
        )
        if SoilHardnessMeasurement.objects.filter(land_block__isnull=True).count() == 0:
            return HttpResponseRedirect(reverse("soil:hardness_association_success"))

        return HttpResponseRedirect(reverse("soil:hardness_association"))


class HardnessAssociationSuccessView(TemplateView):
    template_name = "soil_analysis/hardness/association/success.html"


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
