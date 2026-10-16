"""Ordinary AMQP connections, confirmed publication and early acknowledgement."""
import asyncio
from collections.abc import Mapping
import json
import logging
import os
from typing import Protocol, TypeGuard
from uuid import UUID

import aio_pika
from pamqp.commands import Basic
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from application.quotations.errors import PublicationError
from application.quotations.use_cases import QuotationProcessor

QUEUE_NAME = 'shipping.quotations'
logger = logging.getLogger(__name__)


def _mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, dict)


def get_rabbitmq_url() -> str:
    return os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost/')


class MessageDelivery(Protocol):
    @property
    def body(self) -> bytes: ...
    async def ack(self) -> None: ...


async def handle_delivery(message: MessageDelivery, processor: QuotationProcessor) -> None:
    # Never execute work if acknowledgement fails. Malformed deliveries are also consumed.
    await message.ack()
    try:
        payload: object = json.loads(message.body)
        if not _mapping(payload) or set(payload) != {'quotation_id'}:
            return
        identifier: object = payload['quotation_id']
        if not isinstance(identifier, str):
            return
        quotation_id = UUID(identifier)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return
    await processor.process(quotation_id)


class RabbitMQ:
    def __init__(self, url: str, queue_name: str = QUEUE_NAME) -> None:
        self.url = url
        self.queue_name = queue_name
        self.connection: AbstractConnection | None = None
        self.channel: AbstractChannel | None = None
        self.queue: AbstractQueue | None = None

    async def open(self) -> None:
        self.connection = await aio_pika.connect(self.url, timeout=5)
        try:
            self.channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
            await self.channel.set_qos(prefetch_count=1)
            self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        try:
            if self.channel is not None and not self.channel.is_closed:
                await self.channel.close()
        finally:
            if self.connection is not None and not self.connection.is_closed:
                await self.connection.close()

    async def publish(self, quotation_id: UUID) -> None:
        try:
            if self.channel is None or self.channel.is_closed:
                raise PublicationError('Broker is not connected')
            confirmation = await self.channel.default_exchange.publish(
                aio_pika.Message(json.dumps({'quotation_id': str(quotation_id)}).encode(),
                                 delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                 content_type='application/json'),
                routing_key=self.queue_name, mandatory=True, timeout=5)
            if not isinstance(confirmation, Basic.Ack):
                raise PublicationError('Broker did not acknowledge publication')
        except Exception as error:
            raise PublicationError('Quotation publication was not confirmed') from error

    async def consume(self, processor: QuotationProcessor) -> None:
        if self.queue is None:
            raise RuntimeError('Broker is not connected')
        # basic_get avoids iterator buffering/requeue on cancellation. There is only one
        # delivery at a time, acknowledged before any database/provider work.
        while True:
            message = await self.queue.get(no_ack=False, fail=False)
            if message is None:
                await asyncio.sleep(0.1)
                continue
            await handle_delivery(message, processor)
