export interface DiscordPayload {
  embeds: Array<{
    title: string;
    description: string;
    color: number;
    url?: string;
    fields?: Array<{ name: string; value: string; inline?: boolean }>;
    footer?: { text: string };
    timestamp?: string;
  }>;
}

export function buildDiscordPayload(data: {
  monitorName: string;
  targetUrl: string;
  summary: string;
  eventType: string;
  diffSnippet?: string;
}): DiscordPayload {
  const isDown = data.eventType === 'DOWN';
  const isRecovered = data.eventType === 'RECOVERED';
  const color = isDown ? 0xef4444 : isRecovered ? 0x22c55e : 0x3b82f6; // Red, Green, or Blue

  const fields = [
    { name: 'Target URL', value: data.targetUrl, inline: false },
    { name: 'Event Type', value: data.eventType, inline: true },
  ];

  if (data.diffSnippet) {
    fields.push({
      name: 'Diff Snippet',
      value: `\`\`\`diff\n${data.diffSnippet.slice(0, 1000)}\n\`\`\``,
      inline: false,
    });
  }

  return {
    embeds: [
      {
        title: `ChangeWatch Alert: ${data.monitorName}`,
        description: data.summary,
        color,
        url: data.targetUrl.startsWith('http') ? data.targetUrl : undefined,
        fields,
        footer: { text: 'ChangeWatch — Respectful Website Change Detector' },
        timestamp: new Date().toISOString(),
      },
    ],
  };
}
