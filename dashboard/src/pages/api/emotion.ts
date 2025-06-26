import type { NextApiRequest, NextApiResponse } from 'next';
import amqp from 'amqplib';

const { RABBIT_URL = '' } = process.env;
const QUEUE = 'emotions';

let channel: amqp.Channel | null = null;

async function getChannel() {
  if (channel) return channel;
  const conn = await amqp.connect(RABBIT_URL);
  channel = await conn.createChannel();
  await channel.assertQueue(QUEUE, { durable: true });
  return channel;
}

export default async function handler(
  _req: NextApiRequest,
  res: NextApiResponse
) {
  const ch = await getChannel();
  const msg = await ch.get(QUEUE, { noAck: false });
  if (!msg) return res.status(204).end();          // no new data

  const json = JSON.parse(msg.content.toString());
  ch.ack(msg);
  res.status(200).json(json);
}

