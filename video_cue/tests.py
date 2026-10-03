import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import Resolver404, resolve

from video_cue import views
from video_cue.domain.repository.result_files import ResultFiles, ResultUnavailable
from video_cue.domain.repository.stored_results import StoredResults
from video_cue.domain.valueobject.analysis import Analysis, InvalidAnalysis


def sample() -> dict:
    return {
        "schema_version": 2,
        "input": {"path": "source.mp4", "duration_seconds": 14},
        "highlight_path": "highlights.mp4",
        "events": [
            {
                "start_seconds": 1.8,
                "end_seconds": 4,
                "peak_change_ratio": 0.05,
                "clip_path": "events/event-001.mp4",
                "highlight_start_seconds": 1,
            },
            {
                "start_seconds": 6,
                "end_seconds": 7.6,
                "peak_change_ratio": 0.01,
                "clip_path": "events/event-002.mp4",
                "highlight_start_seconds": 5.2,
            },
        ],
    }


class AnalysisTests(SimpleTestCase):
    """解析 JSON の区間と入力型を検証する。"""

    def test_highlight_result(self):
        """入力: schema 2 の結果。処理: 読み込み。期待値: ハイライト内の位置を保持する。"""
        data = sample()
        result = Analysis.from_dict(data)
        self.assertEqual(result.events[1].highlight_start, 5.2)
        self.assertAlmostEqual(result.events[0].duration, 2.2)

    def test_rejects_invalid_numbers_and_intervals(self):
        """入力: 非数・逆転・範囲外のイベント。処理: 読み込み。期待値: 不正として拒否。"""
        for field, value in [
            ("start_seconds", True),
            ("end_seconds", float("nan")),
            ("end_seconds", float("inf")),
            ("start_seconds", -1),
            ("end_seconds", 1),
            ("end_seconds", 15),
            ("peak_change_ratio", 1.1),
            ("highlight_start_seconds", "1"),
            ("highlight_start_seconds", None),
        ]:
            with self.subTest(field=field, value=value):
                data = sample()
                data["events"][0][field] = value
                with self.assertRaises(InvalidAnalysis):
                    Analysis.from_dict(data)
        data = sample()
        data["events"].reverse()
        with self.assertRaises(InvalidAnalysis):
            Analysis.from_dict(data)

    def test_rejects_invalid_structure(self):
        """入力: 未対応版・欠損・異なる型。処理: 読み込み。期待値: 形式エラー。"""
        for data in [
            None,
            [],
            {},
            {**sample(), "schema_version": True},
            {**sample(), "schema_version": 1},
            {**sample(), "schema_version": 3},
            {**sample(), "events": {}},
            {**sample(), "events": [None]},
        ]:
            with self.subTest(data=data), self.assertRaises(InvalidAnalysis):
                Analysis.from_dict(data)


class StoredViewerTests(SimpleTestCase):
    """隔離した media フォルダーで表示、権限、ファイル配信を検証する。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.result_dir = self.root / "video_cue/0001"
        self.result_dir.mkdir(parents=True)
        self.write(sample())
        (self.result_dir / "highlights.mp4").write_bytes(b"0123456789")
        (self.root / "source.mp4").write_bytes(b"source")
        self.repo = StoredResults(self.root)
        self.factory = RequestFactory()
        self.settings_override = override_settings(MEDIA_ROOT=self.root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def write(self, data):
        (self.result_dir / "analysis.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def request(self, method="get", **headers):
        request = getattr(self.factory, method)("/video_cue/0001/", **headers)
        request.user = SimpleNamespace(
            is_active=True, is_staff=True, is_authenticated=True
        )
        return request

    def test_list_and_player_keep_offsets(self):
        """入力: ハイライト付き結果。処理: 一覧・詳細GET。期待値: 操作と開始位置が表示される。"""
        response = views.index(self.request())
        self.assertContains(response, "録画 0001")
        response = views.detail(self.request(), "0001")
        self.assertContains(response, '"highlight_start": 5.2')
        self.assertContains(response, "/video_cue/0001/media/highlight/")
        self.assertNotContains(response, 'id="show-source"')
        self.assertNotContains(response, 'id="show-highlight"')
        self.assertContains(response, 'id="next-event"')

    def test_empty_result(self):
        """入力: イベント0件。処理: 詳細GET。期待値: 再生動画のない状態を表示する。"""
        data = sample()
        data.update(events=[], highlight_path=None)
        self.write(data)
        self.assertContains(views.detail(self.request(), "0001"), "イベント0件")
        self.assertNotContains(views.detail(self.request(), "0001"), "個別クリップ")

    def test_missing_highlight(self):
        """入力: ハイライト欠損。処理: 詳細GET。期待値: 欠損説明と無効な操作。"""
        (self.result_dir / "highlights.mp4").unlink()
        response = views.detail(self.request(), "0001")
        self.assertContains(response, "ハイライト動画が見つかりません")
        self.assertContains(
            response,
            'class="list-group-item list-group-item-action px-3 py-3 event-button" data-index="0" disabled',
        )

    def test_incomplete_invalid_and_empty_are_distinct(self):
        """入力: 未完了・壊れたJSON・空のmedia。処理: GET。期待値: 409・422・空一覧。"""
        (self.result_dir / "analysis.json").unlink()
        self.assertContains(
            views.detail(self.request(), "0001"), "解析が未完了", status_code=409
        )
        (self.result_dir / "analysis.json").write_text("{broken", encoding="utf-8")
        self.assertContains(
            views.detail(self.request(), "0001"), "JSON が壊れています", status_code=422
        )
        self.assertContains(views.index(self.request()), "JSON が壊れています")
        with override_settings(MEDIA_ROOT=self.root / "empty"):
            response = views.index(self.request())
            self.assertContains(response, "video-cue-engine")
            self.assertContains(response, "元動画のアップロードは不要です")

    def test_oversized_json_is_rejected(self):
        """入力: 上限を超えるJSON。処理: 読み込み。期待値: サイズ制限で拒否。"""
        with patch("video_cue.domain.repository.result_files.MAX_JSON_BYTES", 10):
            with self.assertRaisesMessage(InvalidAnalysis, "上限"):
                self.repo.read("0001")

    def test_unprivileged_cannot_read_pages_or_media(self):
        """入力: ゲスト・一般・無効スタッフ。処理: ページと動画GET。期待値: すべて403。"""
        for user in [
            AnonymousUser(),
            SimpleNamespace(is_active=True, is_staff=False, is_authenticated=True),
            SimpleNamespace(is_active=False, is_staff=True, is_authenticated=True),
        ]:
            request = self.request()
            request.user = user
            for view, args in [
                (views.index, ()),
                (views.detail, ("0001",)),
                (views.media, ("0001",)),
            ]:
                with self.subTest(user=user, view=view):
                    self.assertEqual(view(request, *args).status_code, 403)

    def test_path_escape_and_source_are_rejected(self):
        """入力: 親参照・絶対パス・元動画。処理: 解決。期待値: 配信しない。"""
        for reference in [
            "../source.mp4",
            str(self.root / "source.mp4"),
            "events/../../source.mp4",
        ]:
            with self.subTest(reference=reference):
                self.assertIsNone(self.repo.video("0001", reference))
        with self.assertRaises(ResultUnavailable):
            self.repo.directory("../0001")
        self.assertIsNone(self.repo.video("0001", "source.mp4"))
        with self.assertRaises(Http404):
            views.media(self.request(), "../0001")

    def test_symlink_escape_is_rejected(self):
        """入力: 外側の動画へ向くリンク。処理: 解決。期待値: リンク先を配信しない。"""
        link = self.result_dir / "outside.mp4"
        try:
            link.symlink_to(self.root / "source.mp4")
        except OSError:
            self.skipTest("この環境ではシンボリックリンク作成権限がありません")
        self.assertIsNone(self.repo.video("0001", "outside.mp4"))

    def test_full_partial_suffix_and_head_responses(self):
        """入力: 全体・範囲・末尾・HEAD要求。処理: 動画配信。期待値: 本文と範囲ヘッダー。"""
        for header, expected, content_range in [
            (None, b"0123456789", None),
            ("bytes=2-4", b"234", "bytes 2-4/10"),
            ("bytes=8-", b"89", "bytes 8-9/10"),
            ("bytes=-3", b"789", "bytes 7-9/10"),
            ("bytes=0-999", b"0123456789", "bytes 0-9/10"),
        ]:
            with self.subTest(header=header):
                headers = {"HTTP_RANGE": header} if header else {}
                response = views.media(self.request(**headers), "0001")
                self.assertEqual(response.status_code, 206 if header else 200)
                self.assertEqual(b"".join(response.streaming_content), expected)
                self.assertEqual(response.get("Content-Range"), content_range)
                self.assertEqual(int(response["Content-Length"]), len(expected))
                response.close()
        response = views.media(self.request("head", HTTP_RANGE="bytes=2-4"), "0001")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"")
        self.assertEqual(response["Content-Length"], "3")

    def test_invalid_ranges_and_missing_media(self):
        """入力: 不正範囲・範囲外・欠損動画。処理: 配信。期待値: 416または404。"""
        for header in [
            "bytes=10-",
            "bytes=4-2",
            "bytes=-0",
            "bytes=-",
            "bytes=0-1,3-4",
            "bad",
        ]:
            response = views.media(self.request(HTTP_RANGE=header), "0001")
            self.assertEqual(response.status_code, 416)
            self.assertEqual(response["Content-Range"], "bytes */10")
        (self.result_dir / "highlights.mp4").unlink()
        with self.assertRaises(Http404):
            views.media(self.request(), "0001")

    def test_cancelled_range_closes_file_before_iteration(self):
        """入力: 配信開始前の切断。処理: 応答をclose。期待値: ファイルも閉じる。"""
        stream = (self.result_dir / "highlights.mp4").open("rb")
        with patch.object(Path, "open", return_value=stream), patch.object(
            ResultFiles, "read", return_value=Analysis.from_dict(sample())
        ):
            response = views.media(self.request(HTTP_RANGE="bytes=2-4"), "0001")
        response.close()
        self.assertTrue(stream.closed)

    def test_read_only_routes(self):
        """入力: POST要求。処理: 閲覧エンドポイント。期待値: 405でファイルは変更されない。"""
        before = (self.result_dir / "analysis.json").read_bytes()
        self.assertEqual(views.detail(self.request("post"), "0001").status_code, 405)
        self.assertEqual((self.result_dir / "analysis.json").read_bytes(), before)


class UploadTests(SimpleTestCase):
    """隔離した media でアップロード契約と表示を検証する。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.root,
            VIDEO_CUE_UPLOAD_TOKEN="test-secret",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.factory = RequestFactory()
        self.staff = SimpleNamespace(
            is_active=True, is_staff=True, is_authenticated=True
        )

    def post(self, data=None, *, token="test-secret", key="0001"):
        if data is None:
            data = sample()
        files = {
            "analysis": SimpleUploadedFile(
                "analysis.json",
                json.dumps(data).encode(),
                content_type="application/json",
            )
        }
        if data.get("events"):
            files["highlight"] = SimpleUploadedFile(
                "highlights.mp4",
                b"\x00\x00\x00\x18ftypisomvideo",
                content_type="video/mp4",
            )
        request = self.factory.post(
            f"/video_cue/api/results/{key}/",
            files,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        return views.upload(request, key)

    def request(self, path):
        request = self.factory.get(path)
        request.user = self.staff
        return request

    def test_upload_replay_and_viewer(self):
        """入力: 正常なJSONとMP4を再送。処理: POSTとGET。期待値: 201、200、再生可能。"""
        data = sample()
        data["input"]["path"] = "C:\\private\\source.mp4"
        self.assertEqual(self.post(data).status_code, 201)
        self.assertEqual(self.post(data).status_code, 200)
        self.assertContains(views.index(self.request("/video_cue/")), "録画 0001")
        detail = views.detail(self.request("/video_cue/0001/"), "0001")
        self.assertContains(detail, "/video_cue/0001/media/highlight/")
        self.assertNotContains(detail, "/video_cue/0001/media/source/")
        response = views.media(self.request("/video_cue/0001/media/highlight/"), "0001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            b"".join(response.streaming_content), b"\x00\x00\x00\x18ftypisomvideo"
        )
        response.close()
        saved = StoredResults(self.root).read("0001")
        self.assertEqual(saved.source, "source.mp4")
        self.assertIsNone(
            json.loads(
                (self.root / "video_cue/0001/analysis.json").read_text(encoding="utf-8")
            )["events"][0]["clip_path"]
        )
        self.assertEqual(list((self.root / "video_cue").glob(".upload-*")), [])

    def test_authentication_and_validation(self):
        """入力: 認証失敗・不正JSON・欠損/不正動画。処理: POST。期待値: 拒否し公開しない。"""
        self.assertEqual(self.post(token="wrong").status_code, 401)
        for data in [
            {**sample(), "events": {}},
            {**sample(), "highlight_path": "../x.mp4"},
            {**sample(), "schema_version": 1},
            {**sample(), "input": {"path": "/", "duration_seconds": 14}},
        ]:
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 422)
        files = {
            "analysis": SimpleUploadedFile(
                "analysis.json", json.dumps(sample()).encode()
            )
        }
        request = self.factory.post(
            "/video_cue/api/results/0001/",
            files,
            HTTP_AUTHORIZATION="Bearer test-secret",
        )
        self.assertEqual(views.upload(request, "0001").status_code, 422)
        files["highlight"] = SimpleUploadedFile("highlights.mp4", b"not-mp4")
        request = self.factory.post(
            "/video_cue/api/results/0001/",
            files,
            HTTP_AUTHORIZATION="Bearer test-secret",
        )
        self.assertEqual(views.upload(request, "0001").status_code, 422)
        self.assertEqual(StoredResults(self.root).list(), [])

    def test_conflict_preserves_original(self):
        """入力: 同一IDで異なる結果。処理: 再送。期待値: 409で既存の結果を保持。"""
        self.assertEqual(self.post().status_code, 201)
        original = (self.root / "video_cue/0001/analysis.json").read_bytes()
        changed = sample()
        changed["input"]["duration_seconds"] = 20
        self.assertEqual(self.post(changed).status_code, 409)
        self.assertEqual(
            (self.root / "video_cue/0001/analysis.json").read_bytes(), original
        )
        self.assertEqual(list((self.root / "video_cue").glob(".upload-*")), [])

    def test_zero_events_and_size_limit(self):
        """入力: イベント0件と容量超過。処理: POST。期待値: JSONのみ登録、超過分は拒否。"""
        empty = sample()
        empty.update(events=[], highlight_path=None)
        self.assertEqual(self.post(empty).status_code, 201)
        self.assertFalse((self.root / "video_cue/0001/highlights.mp4").exists())
        self.assertContains(
            views.detail(self.request("/video_cue/0001/"), "0001"), "イベント0件"
        )
        with patch("video_cue.domain.repository.stored_results.MAX_HIGHLIGHT_BYTES", 4):
            self.assertEqual(self.post(key="0002").status_code, 413)
        self.assertFalse((self.root / "video_cue/0002").exists())

    def test_failed_publish_leaves_no_partial_result(self):
        """入力: 公開時のディスク障害。処理: POST。期待値: 503で一時成果物も一覧に残らない。"""
        with patch(
            "video_cue.domain.repository.stored_results.os.rename",
            side_effect=OSError("disk"),
        ):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(StoredResults(self.root).list(), [])
        self.assertEqual(list((self.root / "video_cue").iterdir()), [])

    def test_direct_media_url_is_not_public(self):
        """入力: 保存領域の直リンク。処理: Django URL解決。期待値: 認可済み配信を迂回しない。"""
        self.assertEqual(self.post().status_code, 201)
        match = resolve("/media/video_cue/0001/highlights.mp4")
        self.assertEqual(
            match.func(
                self.factory.get(match.route), "0001/highlights.mp4"
            ).status_code,
            404,
        )

    def test_source_and_clip_routes_do_not_exist(self):
        """入力: 元動画・個別クリップの旧URL。処理: URL解決。期待値: 404。"""
        for path in (
            "/video_cue/0001/media/source/",
            "/video_cue/0001/media/0/",
        ):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)

    def test_only_media_root_is_listed(self):
        """入力: media 外の旧結果と保存済み結果。処理: 一覧。期待値: 保存済みだけ表示。"""
        legacy = self.root / "legacy/other"
        legacy.mkdir(parents=True)
        (legacy / "analysis.json").write_text(json.dumps(sample()), encoding="utf-8")
        self.assertEqual(self.post().status_code, 201)
        listing = views.index(self.request("/video_cue/"))
        self.assertContains(listing, "録画 0001")
        self.assertNotContains(listing, "録画 other")
