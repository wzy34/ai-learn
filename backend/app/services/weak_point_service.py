from app.models.user import WeakPointStat, WeakPointSummary
from app.repositories.quiz_repository import QuizRepository, get_quiz_repository

WEAK_POINT_REPORT_LIMIT = 20
WEAK_POINT_RESULT_LIMIT = 5

# Reports may contain placeholder entries when nothing was actually weak.
_PLACEHOLDER_WEAK_POINTS = {"无", "暂无", "无薄弱点", "无明显薄弱点"}


class WeakPointService:
    """Aggregate weak knowledge points from the user's recent reports."""

    def __init__(self, repository: QuizRepository | None = None) -> None:
        self._repository = repository or get_quiz_repository()

    async def get_weak_points(self, user_id: int) -> WeakPointSummary:
        entries = await self._repository.list_recent_reports(
            user_id=user_id,
            limit=WEAK_POINT_REPORT_LIMIT,
        )
        return self._aggregate(entries)

    @staticmethod
    def _aggregate(entries: list) -> WeakPointSummary:
        # Entries arrive newest-first, so ties below keep the most recent
        # report's ordering.
        stats: dict[str, WeakPointStat] = {}
        for entry in entries:
            for point in entry.report.weak_points:
                normalized = point.strip()
                if not normalized or normalized in _PLACEHOLDER_WEAK_POINTS:
                    continue
                existing = stats.get(normalized)
                if existing is None:
                    stats[normalized] = WeakPointStat(
                        point=normalized,
                        count=1,
                        last_seen_at=entry.created_at,
                    )
                else:
                    stats[normalized] = existing.model_copy(
                        update={"count": existing.count + 1}
                    )

        items = sorted(stats.values(), key=lambda stat: -stat.count)[
            :WEAK_POINT_RESULT_LIMIT
        ]
        return WeakPointSummary(items=items, total_reports=len(entries))


_weak_point_service: WeakPointService | None = None


def get_weak_point_service() -> WeakPointService:
    """Get the shared weak-point aggregation service."""

    global _weak_point_service
    if _weak_point_service is None:
        _weak_point_service = WeakPointService()
    return _weak_point_service
