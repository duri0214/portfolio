import json
import os
import shutil

from django.contrib import messages
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management import call_command
from django.db.models import Count, Prefetch
from django.http import HttpResponseRedirect, JsonResponse
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

from lib.geo.valueobject.coords import GoogleMapCoords
from lib.zipfileservice import ZipFileService
from soil_analysis.domain.repository.landrepository import LandRepository
from soil_analysis.domain.service.geocode.yahoo import ReverseGeocoderService
from soil_analysis.domain.service.landcandidateservice import LandCandidateService
from soil_analysis.domain.service.reports.reportlayout1 import ReportLayout1
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
        company = Company(pk=self.kwargs["company_id"])
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
        company = Company.objects.get(pk=self.kwargs["company_id"])
        land_repository = LandRepository(company)
        land_ledger_map = {
            land: land_repository.read_land_ledgers(land)
            for land in context["object_list"]
        }
        context["company"] = company
        context["land_ledger_map"] = land_ledger_map

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

        coords = GoogleMapCoords(latitude=lat, longitude=lon)
        ydf = ReverseGeocoderService.get_ydf_from_coords(coords)

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
            shutil.rmtree(upload_folder)

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
        return (
            super()
            .get_queryset()
            .filter(land_block__isnull=True)
            .values("set_memory", "set_datetime")
            .annotate(cnt=Count("pk"))
            .order_by("set_memory")
        )

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
        form_land_ledger = int(request.POST.get("land_ledger")[0])
        if "btn_individual" in request.POST:
            return HttpResponseRedirect(
                reverse(
                    "soil:hardness_association_individual",
                    kwargs={
                        "memory_anchor": int(request.POST.get("btn_individual")),
                        "land_ledger": form_land_ledger,
                    },
                )
            )

        form_checkboxes = [
            int(checkbox) for checkbox in request.POST.getlist("form_checkboxes[]")
        ]
        if form_checkboxes:
            land_ledger = LandLedger.objects.filter(pk=form_land_ledger).first()
            sampling_times = land_ledger.sampling_method.times
            total_sampling_times = 5 * sampling_times
            needle = 0
            land_block_orders = SamplingOrder.objects.filter(
                sampling_method=land_ledger.sampling_method
            ).order_by("ordering")
            for memory_anchor in form_checkboxes:
                hardness_measurements = SoilHardnessMeasurement.objects.filter(
                    set_memory__range=(
                        memory_anchor,
                        memory_anchor + (total_sampling_times - 1),
                    )
                ).order_by("pk")
                for i, hardness_measurement in enumerate(hardness_measurements):
                    hardness_measurement.land_block = land_block_orders[
                        needle
                    ].land_block
                    hardness_measurement.land_ledger = land_ledger
                    forward_the_needle = (
                        i > 0
                        and i % (hardness_measurement.setdepth * sampling_times) == 0
                    )
                    if forward_the_needle:
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
        form_land_ledger = self.kwargs.get("land_ledger")
        land_ledger = LandLedger.objects.filter(pk=form_land_ledger).first()
        total_sampling_times = 5 * land_ledger.sampling_method.times
        return (
            super()
            .get_queryset()
            .filter(
                set_memory__range=(
                    form_memory_anchor,
                    form_memory_anchor + (total_sampling_times - 1),
                )
            )
            .values("set_memory", "set_datetime")
            .annotate(cnt=Count("pk"))
            .order_by("set_memory")
        )

    def get_context_data(self, **kwargs):
        form_memory_anchor = self.kwargs.get("memory_anchor")
        form_land_ledger = self.kwargs.get("land_ledger")
        context = super().get_context_data(**kwargs)
        context["memory_anchor"] = form_memory_anchor
        context["land_ledger"] = form_land_ledger
        context["land_blocks"] = LandBlock.objects.order_by("pk").all()
        return context

    def post(self, request, **kwargs):
        """
        R型 以外で登録したいとき
        フォームから25レコードの情報がくるのでそれぞれを更新する
        """
        form_memory_anchor = self.kwargs.get("memory_anchor")
        form_land_ledger = self.kwargs.get("land_ledger")
        form_land_blocks = request.POST.getlist("land-blocks[]")
        land_ledger = LandLedger.objects.filter(pk=form_land_ledger).first()
        total_sampling_times = 5 * land_ledger.sampling_method.times
        hardness_measurements = SoilHardnessMeasurement.objects.filter(
            set_memory__range=(
                form_memory_anchor,
                form_memory_anchor + (total_sampling_times - 1),
            )
        ).order_by("pk")
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
        upload_file: InMemoryUploadedFile = self.request.FILES["file"]
        kml_raw = upload_file.read()
        land_candidate_service = LandCandidateService()
        land_candidates = land_candidate_service.parse_kml(kml_raw).list()

        if len(land_candidates) < 2:
            messages.error(self.request, "少なくとも 2 つの場所を指定してください")
            return redirect(self.request.META.get("HTTP_REFERER"))

        if len(land_candidates) > 10:
            messages.error(
                self.request,
                "GoogleMapAPIのレート上昇制約により 10 地点までしか計算できません",
            )
            return redirect(self.request.META.get("HTTP_REFERER"))

        entities = []
        for land_candidate in land_candidates:
            coordinates_str = land_candidate.center.to_googlemap().to_str()
            entity = RouteSuggestImport.objects.create(
                name=land_candidate.name, coords=coordinates_str
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
            land_list.append({"name": land_name, "coords": route_suggest_import.coords})

        context["company_list"] = company_list
        context["land_list"] = land_list
        context["coords_list"] = list(land["coords"] for land in land_list)
        context["google_maps_api_key"] = os.getenv("GOOGLE_MAPS_API_KEY")

        return context
