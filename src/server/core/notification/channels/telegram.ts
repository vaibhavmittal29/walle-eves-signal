export function buildTelegramMessage(data: {
  monitorName: string;
  targetUrl: string;
  summary: string;
  eventType: string;
  diffSnippet?: string;
}): string {
  const icon = data.eventType === 'DOWN' ? '🔴' : data.eventType === 'RECOVERED' ? '🟢' : '🔔';

  let msg = `${icon} *ChangeWatch Alert*: *${data.monitorName}*\n`;
  msg += `*Event*: \`${data.eventType}\`\n`;
  msg += `*URL*: ${data.targetUrl}\n`;
  msg += `*Summary*: ${data.summary}\n`;

  if (data.diffSnippet) {
    msg += `\n*Changes*:\n\`\`\`\n${data.diffSnippet.slice(0, 500)}\n\`\`\`\n`;
  }

  return msg;
}
