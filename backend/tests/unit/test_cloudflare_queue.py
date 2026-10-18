"""Queue contract: awaited publication and acknowledgement before work."""

import asyncio
import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from adapters.queue.cloudflare import CloudflareQuotationPublisher, handle_message
from application.quotations.errors import PublicationError
from application.quotations.use_cases import QuotationProcessor


class Message:
    def __init__(self, payload: object, events: list[str], fail: bool = False) -> None:
        self.payload = payload
        self.events = events
        self.fail = fail

    def ack(self) -> None:
        self.events.append("ack")
        if self.fail:
            raise RuntimeError("ack failed")

    @property
    def body(self) -> object:
        self.events.append("body")
        return self.payload


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_is_awaited_once_and_only_contains_identifier(self):
        started = asyncio.Event()
        release = asyncio.Event()
        queue = AsyncMock()
        identifier = uuid4()

        async def send(payload):
            self.assertEqual(payload, {"quotation_id": str(identifier)})
            started.set()
            await release.wait()

        queue.send.side_effect = send
        task = asyncio.create_task(
            CloudflareQuotationPublisher(lambda: queue).publish(identifier)
        )
        await started.wait()
        self.assertFalse(task.done())
        release.set()
        await task
        queue.send.assert_awaited_once()

    async def test_send_failure_maps_to_publication_error(self):
        queue = AsyncMock()
        queue.send.side_effect = OSError("private binding error")
        with self.assertRaises(PublicationError):
            await CloudflareQuotationPublisher(lambda: queue).publish(uuid4())
        queue.send.assert_awaited_once()

    async def test_ack_precedes_body_and_processing(self):
        events = []
        processor = AsyncMock(spec=QuotationProcessor)
        identifier = uuid4()

        async def process(value):
            events.append("process")
            self.assertEqual(value, identifier)
            self.assertEqual(events, ["ack", "body", "process"])

        processor.process.side_effect = process
        await handle_message(
            Message({"quotation_id": str(identifier)}, events), processor
        )
        processor.process.assert_awaited_once_with(identifier)

    async def test_failed_ack_never_reads_body_or_starts(self):
        events = []
        processor = AsyncMock(spec=QuotationProcessor)
        with self.assertRaisesRegex(RuntimeError, "ack failed"):
            await handle_message(
                Message({"quotation_id": str(uuid4())}, events, True), processor
            )
        self.assertEqual(events, ["ack"])
        processor.process.assert_not_awaited()

    async def test_malformed_payloads_are_acknowledged_and_ignored(self):
        for payload in (
            None,
            b"{}",
            "{}",
            [],
            {},
            {"quotation_id": 1},
            {"quotation_id": "bad"},
            {"quotation_id": str(uuid4()), "extra": 1},
        ):
            with self.subTest(payload=payload):
                events = []
                processor = AsyncMock(spec=QuotationProcessor)
                await handle_message(Message(payload, events), processor)
                self.assertEqual(events, ["ack", "body"])
                processor.process.assert_not_awaited()
