// Privacy: display-only anonymization of real vendor/company names (e.g.
// "loghub", "Microsoft", "Fortinet", "nginx" -- real values from this
// deployment's real seeded sources/parsers). The real `vendor` field is
// untouched everywhere else (filtering, backend calls, source_pack lookup,
// parser execution) -- only what's rendered on screen is swapped for a
// stable, generic label, so a screenshot/demo never shows a real vendor or
// company name. Deterministic per key, so the same source/parser always
// shows the same fake label.
export function anonymizedVendorLabel(key: string): string {
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  return `Vendor ${letters[hash % letters.length]}${(hash % 90 + 10)}`
}

// Some real Source rows were named with a provenance note in parentheses
// (e.g. "FortiGate Firewall (real vendor sample)") -- useful in the DB but
// noisy as a card title. Strips a single trailing "(...)" for display only;
// the real `name` field (used for search/filter matching) is untouched.
export function displaySourceName(name: string): string {
  return name.replace(/\s*\([^)]*\)\s*$/, '').trim() || name
}
