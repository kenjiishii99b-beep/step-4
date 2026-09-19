import asyncio
import time
from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class _Bucket:
    failure_count: int = 0
    locked_until: float | None = None


@dataclass
class _AttemptState:
    staff_buckets: dict[str, _Bucket] = field(default_factory=dict)
    ip_buckets: dict[str, _Bucket] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class LoginRateLimiter:
    """同一 staff_id / IP アドレス単位のログイン試行制限（設計仕様書 3.2 節）。

    staff_id 単位のロックは「同一アカウントへの総当たり」を防ぐための厳しい
    しきい値、IP 単位のロックは「同一拠点からの大量試行」を防ぐためのより
    緩いしきい値として、意図的に別々のしきい値を持つ（3.2節の「併用」は
    同一しきい値の重複適用を意味しない。多数のスタッフが同一店舗の共有
    IPからログインするため、IP側を厳しくしすぎると無関係なスタッフを
    巻き込んでロックしてしまう）。

    プロセス内メモリで状態を保持するため、複数バックエンドインスタンスに
    スケールアウトする場合は Redis 等の共有ストアに置き換える必要がある。
    """

    def __init__(
        self,
        max_staff_failures: int,
        max_ip_failures: int,
        lockout_seconds: float,
    ) -> None:
        self._max_staff_failures = max_staff_failures
        self._max_ip_failures = max_ip_failures
        self._lockout_seconds = lockout_seconds
        self._state = _AttemptState()

    async def seconds_until_unlocked(self, staff_id: str, ip_address: str) -> float | None:
        async with self._state.lock:
            now = time.monotonic()
            candidates = (
                self._state.staff_buckets.get(staff_id),
                self._state.ip_buckets.get(ip_address),
            )
            remaining = [
                bucket.locked_until - now
                for bucket in candidates
                if bucket is not None
                and bucket.locked_until is not None
                and bucket.locked_until > now
            ]
            return max(remaining) if remaining else None

    async def record_failure(self, staff_id: str, ip_address: str) -> None:
        async with self._state.lock:
            now = time.monotonic()
            for buckets, key, max_failures in (
                (self._state.staff_buckets, staff_id, self._max_staff_failures),
                (self._state.ip_buckets, ip_address, self._max_ip_failures),
            ):
                bucket = buckets.setdefault(key, _Bucket())
                if bucket.locked_until is not None and bucket.locked_until <= now:
                    bucket.failure_count = 0
                    bucket.locked_until = None
                bucket.failure_count += 1
                if bucket.failure_count >= max_failures:
                    bucket.locked_until = now + self._lockout_seconds

    async def reset(self, staff_id: str, ip_address: str) -> None:
        async with self._state.lock:
            self._state.staff_buckets.pop(staff_id, None)
            self._state.ip_buckets.pop(ip_address, None)


login_rate_limiter = LoginRateLimiter(
    max_staff_failures=settings.LOGIN_MAX_FAILURES,
    max_ip_failures=settings.LOGIN_MAX_FAILURES_PER_IP,
    lockout_seconds=settings.LOGIN_LOCKOUT_MINUTES * 60,
)
