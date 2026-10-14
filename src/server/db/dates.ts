/**
 * Formats a JavaScript Date object to standard SQLite datetime string: 'YYYY-MM-DD HH:MM:SS'
 */
export function toSqliteDateTime(d: Date = new Date()): string {
  return d.toISOString().replace('T', ' ').slice(0, 19);
}
