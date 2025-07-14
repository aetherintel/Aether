export type Channel = {
  channel_id: string;
  username: string;
  title: string | null;
  message_count: number;
  last_message_date: string;
  recommended_by: number;
  is_scraped: boolean | null;
  scraped_at: string | null;
};

export type GroupedChannelStructure = Record<string, string[]>;

export type OutputChannelStructure = Record<
  string,
  {
    channel: Channel | null;
    recommended: Record<string, { channel: Channel }>;
  }
>;

export type OutputChannelEntry = OutputChannelStructure[string];
