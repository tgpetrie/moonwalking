import type { RawPost } from '../../../packages/core/src/index'

export interface Connector {
  name: string
  pullSince(sinceTs: number): Promise<RawPost[]>
}

export class DiscordConnector implements Connector {
  name = 'discord'
  constructor(
    private token: string,
    private channelIds: string[]
  ) {}
  async pullSince(sinceTs: number): Promise<RawPost[]> {
    // TODO: implement Discord API calls; return mapped RawPost[]
    return []
  }
}

export class RedditConnector implements Connector {
  name = 'reddit'
  constructor(
    private clientId: string,
    private secret: string,
    private subs: string[]
  ) {}
  async pullSince(sinceTs: number): Promise<RawPost[]> {
    // TODO: implement Reddit OAuth + fetch new posts/comments; return RawPost[]
    return []
  }
}

export class TelegramConnector implements Connector {
  name = 'telegram'
  constructor(
    private botToken: string,
    private chatIds: string[]
  ) {}
  async pullSince(sinceTs: number): Promise<RawPost[]> {
    // TODO: implement Telegram Bot API; return RawPost[]
    return []
  }
}
