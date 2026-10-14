export interface EmailNotificationPayload {
  to: string;
  subject: string;
  html: string;
  text: string;
}

export function buildEmailMessage(data: {
  recipientEmail: string;
  monitorName: string;
  targetUrl: string;
  summary: string;
  eventType: string;
  diffSnippet?: string;
}): EmailNotificationPayload {
  const subject = `[ChangeWatch] ${data.eventType}: ${data.monitorName}`;

  const text = `
ChangeWatch Notification
========================
Monitor: ${data.monitorName}
Event: ${data.eventType}
URL: ${data.targetUrl}
Summary: ${data.summary}

${data.diffSnippet ? `Changes:\n${data.diffSnippet}` : ''}
`.trim();

  const html = `
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f17; color: #f3f4f6; padding: 20px; }
    .card { background-color: #111827; border: 1px solid #374151; border-radius: 8px; padding: 24px; max-width: 600px; margin: 0 auto; }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; background-color: #3b82f6; color: white; }
    .diff { background-color: #1f2937; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; white-space: pre-wrap; margin-top: 16px; border: 1px solid #4b5563; }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">${data.eventType}</span>
    <h2>${data.monitorName}</h2>
    <p><strong>Target:</strong> <a href="${data.targetUrl}" style="color: #60a5fa;">${data.targetUrl}</a></p>
    <p>${data.summary}</p>
    ${data.diffSnippet ? `<div class="diff">${data.diffSnippet}</div>` : ''}
  </div>
</body>
</html>
`.trim();

  return {
    to: data.recipientEmail,
    subject,
    html,
    text,
  };
}
