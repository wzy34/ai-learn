from app.models.report import ReportResponse
from app.models.user import WeakPointSummary
from app.services.weak_point_service import WeakPointService


def _report(weak_points):
    return ReportResponse(
        accuracy=80,
        mastered_points=["RAG 定义"],
        weak_points=weak_points,
        three_line_summary=["第一点", "第二点", "第三点"],
        advice=["继续学习"],
        share_quote="继续闯关。",
    )


def _entry(weak_points, created_at):
    class _Entry:
        pass

    entry = _Entry()
    entry.report = _report(weak_points)
    entry.created_at = created_at
    return entry


def test_weak_points_are_counted_across_reports_with_newest_first_ties():
    entries = [
        _entry(["向量数据库", "RAG 流程"], "2026-08-29 10:00:00"),
        _entry(["RAG 流程", "分块策略"], "2026-08-28 09:00:00"),
        _entry(["向量数据库"], "2026-08-27 08:00:00"),
    ]

    summary = WeakPointService._aggregate(entries)

    assert isinstance(summary, WeakPointSummary)
    assert summary.total_reports == 3
    assert [(stat.point, stat.count) for stat in summary.items] == [
        ("向量数据库", 2),
        ("RAG 流程", 2),
        ("分块策略", 1),
    ]
    # Ties keep the newest report's ordering, and last_seen_at reflects the
    # most recent report containing the point.
    assert summary.items[0].last_seen_at == "2026-08-29 10:00:00"
    assert summary.items[1].last_seen_at == "2026-08-29 10:00:00"


def test_placeholder_weak_points_are_ignored():
    entries = [_entry(["无", "  ", "向量数据库"], "2026-08-29 10:00:00")]

    summary = WeakPointService._aggregate(entries)

    assert [stat.point for stat in summary.items] == ["向量数据库"]


def test_weak_points_are_capped_and_blank_reports_are_tolerated():
    entries = [
        _entry([f"知识点{i}" for i in range(10)], "2026-08-29 10:00:00"),
        _entry([], "2026-08-28 09:00:00"),
    ]

    summary = WeakPointService._aggregate(entries)

    assert summary.total_reports == 2
    assert len(summary.items) == 5
    assert summary.items[0].point == "知识点0"
