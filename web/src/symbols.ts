// Trade symbols in run artifacts are bare A-share codes ("600000"); lake
// partitions are exchange-prefixed ("SH600000"). Map a traded symbol to
// ordered lake candidates and probe them until one has bars.

const EXCHANGE_PREFIX = /^(SH|SZ|BJ)/;

export function lakeSymbolCandidates(raw: string): string[] {
  const code = raw.trim().toUpperCase();
  if (!code) return [];
  if (EXCHANGE_PREFIX.test(code)) return [code];
  if (/^6/.test(code)) return [`SH${code}`, `SZ${code}`];
  if (/^[03]/.test(code)) return [`SZ${code}`, `SH${code}`];
  if (/^[48]/.test(code)) return [`BJ${code}`, `SH${code}`];
  return [code];
}
