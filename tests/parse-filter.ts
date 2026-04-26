// Canonical Cribl filter shape we can auto-resolve: `<field>=='<value>'`.
// Anything more complex (boolean ops, function calls, regex) is out of scope
// for the local evaluator — callers should it.skip when this returns null.
const SIMPLE_FILTER_RE = /^\s*([A-Za-z_]\w*)\s*==\s*['"](.*?)['"]\s*$/;

/**
 * Parse `<field>=='<value>'` (or `=="<value>"`) into [field, value].
 * Returns null for any expression we cannot statically resolve.
 */
export function parseSimpleFilter(
  expr: string | null | undefined,
): [string, string] | null {
  const match = (expr ?? "").match(SIMPLE_FILTER_RE);
  if (!match || match[1] === undefined || match[2] === undefined) {
    return null;
  }
  return [match[1], match[2]];
}
