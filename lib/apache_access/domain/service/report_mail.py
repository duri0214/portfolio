"""Build plain-text and HTML bodies for an Apache access report."""

from html import escape
from zoneinfo import ZoneInfo

from lib.apache_access.domain.valueobject.report import ApacheAccessReport


TOKYO = ZoneInfo("Asia/Tokyo")


class ApacheAccessReportMailService:
    """Build identifier-free plain-text and HTML messages from a report."""

    def build_bodies(self, report: ApacheAccessReport) -> tuple[str, str]:
        """Build identifier-free plain-text and HTML messages from a report."""
        period_start = report.period_start.astimezone(TOKYO).strftime(
            "%Y-%m-%d %H:%M JST"
        )
        period_end = report.period_end.astimezone(TOKYO).strftime("%Y-%m-%d %H:%M JST")
        generated_at = report.generated_at.astimezone(TOKYO).strftime(
            "%Y-%m-%d %H:%M JST"
        )
        rows = (
            ("リクエスト総数", report.total_requests),
            ("401", report.status_401),
            ("403", report.status_403),
            ("404", report.status_404),
            ("5xx", report.status_5xx),
            ("失敗応答の送信元数", report.failure_sources),
            ("一つの送信元に集中した失敗応答の最大件数", report.top_source_failures),
            ("ログイン先へのリクエスト", report.login_requests),
            (
                "一つの送信元からのログイン先リクエストの最大件数",
                report.top_source_login_requests,
            ),
            ("要注意パス候補への 2xx", report.sensitive_path_successes),
            ("失敗応答（期間前半）", report.previous_failures),
            ("失敗応答（期間後半）", report.recent_failures),
            ("解析できなかったログ行数", report.malformed_lines),
        )
        text_rows = "\n".join(f"{label}: {value}" for label, value in rows)
        body = (
            "Apache アクセス傾向レポート\n"
            f"対象期間: {period_start} ～ {period_end}\n"
            f"集計時刻: {generated_at}\n\n"
            f"{text_rows}\n\n"
            "これらの数値は調査のきっかけであり、攻撃や情報漏えいを確定するものではありません。"
        )
        html_rows = "".join(
            f"<tr><td>{escape(label)}</td><td>{value}</td></tr>"
            for label, value in rows
        )
        html_body = (
            '<!doctype html><html lang="ja"><body>'
            "<h1>Apache アクセス傾向レポート</h1>"
            f"<p>対象期間: {escape(period_start)} ～ {escape(period_end)}<br>"
            f"集計時刻: {escape(generated_at)}</p>"
            f'<table border="1" cellpadding="6">{html_rows}</table>'
            "<p>これらの数値は調査のきっかけであり、攻撃や情報漏えいを確定するものではありません。</p>"
            "</body></html>"
        )
        return body, html_body
