/** Decode the `data:` fields of one blank-line-delimited Server-Sent Event frame. */
export function decodeSseFrame(frame: string): string | null {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith(':'))
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''))
    .join('\n');
  return data || null;
}
