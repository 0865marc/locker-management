"""SQLite round trips, database invariants and rollback of custody writes."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest
from uuid import uuid4

from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from adapters.database.connection import create_database
from adapters.database.sqlmodel_repositories import SqlModelDeliveryRepository, SqlModelReturnRepository
from domain.models import Delivery, Return

NOW = datetime(2026, 10, 14, 12, 30, 25, 123456, tzinfo=timezone.utc)


def delivery(**kwargs):
    return Delivery(tracking_number="TRACK-1", carrier_code="carrier-a", recipient_name="Ana", received_at=NOW, **kwargs)


def returned(**kwargs):
    return Return(tracking_number="TRACK-1", carrier_code="carrier-a", received_at=NOW, **kwargs)


REPOSITORIES = ((delivery, SqlModelDeliveryRepository, "collect"), (returned, SqlModelReturnRepository, "hand_over"))


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine, self.sessions = create_database("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_complete_round_trip_from_new_instances(self):
        examples = [
            (SqlModelDeliveryRepository, [delivery(), delivery(recipient_phone="+34600123456", pickup_deadline_at=NOW.astimezone(timezone(timedelta(hours=2)))).return_to_carrier(NOW + timedelta(seconds=1))]),
            (SqlModelReturnRepository, [returned(), returned(sender_name="María").hand_over(NOW + timedelta(seconds=2))]),
        ]
        for repository_class, records in examples:
            repository = repository_class(self.sessions)
            self.assertEqual(await repository.list_all(), [])
            self.assertIsNone(await repository.get_by_id(uuid4()))
            for record in records:
                await repository.save(record)
            fresh = repository_class(self.sessions)
            self.assertCountEqual(await fresh.list_all(), records)
            for record in records:
                actual = await fresh.get_by_id(record.id)
                self.assertEqual(actual, record)
                self.assertEqual(actual.received_at.tzinfo, timezone.utc)

    async def test_duplicate_uuid_rollback_leaves_original_and_allows_next_write(self):
        for factory, repository_class, _ in REPOSITORIES:
            repository = repository_class(self.sessions)
            original = factory()
            await repository.save(original)
            with self.assertRaises(IntegrityError):
                await repository.save(replace(original, tracking_number="Different"))
            following = factory()
            await repository.save(following)
            self.assertCountEqual(await repository.list_all(), [original, following])

    async def test_exit_only_changes_custody_and_cannot_overwrite_winner(self):
        for factory, repository_class, transition in REPOSITORIES:
            repository = repository_class(self.sessions)
            original = factory()
            await repository.save(original)
            first = getattr(original, transition)(NOW + timedelta(seconds=1))
            second = getattr(original, transition)(NOW + timedelta(seconds=2))
            # Persistence never copies stale reception or contact data from the contender.
            self.assertTrue(await repository.save_exit(replace(first, tracking_number="Ignored")))
            self.assertFalse(await repository.save_exit(second))
            self.assertEqual(await repository_class(self.sessions).get_by_id(original.id), first)
            self.assertFalse(await repository.save_exit(replace(second, id=uuid4())))

    async def test_incompatible_delivery_exit_preserves_winning_timestamp(self):
        repository = SqlModelDeliveryRepository(self.sessions)
        original = delivery()
        await repository.save(original)
        winner = original.return_to_carrier(NOW + timedelta(seconds=1))
        self.assertTrue(await repository.save_exit(winner))
        self.assertFalse(await repository.save_exit(original.collect(NOW + timedelta(seconds=2))))
        self.assertEqual(await repository.get_by_id(original.id), winner)

    async def test_failed_commit_rolls_back_transition_and_later_exit_succeeds(self):
        def fail_commit(session):
            raise RuntimeError("Simulated failure before commit")

        for factory, repository_class, transition in REPOSITORIES:
            repository = repository_class(self.sessions)
            original = factory()
            await repository.save(original)
            terminal = getattr(original, transition)(NOW + timedelta(seconds=1))
            event.listen(Session, "before_commit", fail_commit)
            try:
                with self.assertRaisesRegex(RuntimeError, "before commit"):
                    await repository.save_exit(terminal)
            finally:
                event.remove(Session, "before_commit", fail_commit)
            self.assertEqual(await repository.get_by_id(original.id), original)
            self.assertTrue(await repository.save_exit(terminal))
            self.assertEqual(await repository.get_by_id(original.id), terminal)

    async def test_database_rejects_invalid_states_dates_and_exit_combinations(self):
        for factory, repository_class, _ in REPOSITORIES:
            original = factory()
            await repository_class(self.sessions).save(original)
        invalid_updates = [
            "UPDATE deliveries SET status = 'UNKNOWN'",
            "UPDATE deliveries SET status = 'COLLECTED'",
            "UPDATE deliveries SET status = 'COLLECTED', collected_at = '2020-01-01', returned_to_carrier_at = '2026-10-15'",
            "UPDATE deliveries SET status = 'COLLECTED', collected_at = '2020-01-01'",
            "UPDATE deliveries SET status = 'RETURNED_TO_CARRIER', returned_to_carrier_at = '2020-01-01'",
            "UPDATE returns SET status = 'UNKNOWN'",
            "UPDATE returns SET status = 'HANDED_OVER'",
            "UPDATE returns SET status = 'HANDED_OVER', handed_over_at = '2020-01-01'",
        ]
        for statement in invalid_updates:
            with self.subTest(statement=statement), self.assertRaises(IntegrityError):
                async with self.sessions.begin() as session:
                    await session.exec(text(statement))
        self.assertEqual((await SqlModelDeliveryRepository(self.sessions).list_all())[0].status.value, "AWAITING_PICKUP")
        self.assertEqual((await SqlModelReturnRepository(self.sessions).list_all())[0].status.value, "AWAITING_CARRIER")
