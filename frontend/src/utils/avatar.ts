// -----------------------------------------------------------------------------
// Gravatar helper — uses the Chinese mirror `https://gravatar.webp.se/` to
// avoid gravatar.com being unreachable from some networks.
//
// Gravatar URL format:
//   https://gravatar.webp.se/avatar/<md5(lowercase(trim(email)))>?s=<size>&d=identicon
//
// `avatar_url` precedence:
//   1. If backend provides a non-empty `avatar_url` — use it as-is.
//   2. Otherwise, if `email` is known — compute gravatar URL.
//   3. Otherwise return `undefined` (Avatar will show the fallback icon).
// -----------------------------------------------------------------------------

const GRAVATAR_ENDPOINT = 'https://gravatar.webp.se/avatar/';

/**
 * Self-contained MD5. Public-domain implementation by Paul Johnston (2000)
 * — kept tiny inline so we don't pull in a whole npm package just for avatars.
 */
function md5(input: string): string {
  const rhex = (n: number) => {
    const hex = '0123456789abcdef';
    let s = '';
    for (let j = 0; j < 4; j++) {
      s += hex.charAt((n >> (j * 8 + 4)) & 0x0f) + hex.charAt((n >> (j * 8)) & 0x0f);
    }
    return s;
  };

  const addUnsigned = (x: number, y: number) => {
    const lsw = (x & 0xffff) + (y & 0xffff);
    const msw = (x >> 16) + (y >> 16) + (lsw >> 16);
    return (msw << 16) | (lsw & 0xffff);
  };

  const rol = (n: number, c: number) => (n << c) | (n >>> (32 - c));

  const cmn = (q: number, a: number, b: number, x: number, s: number, t: number) =>
    addUnsigned(rol(addUnsigned(addUnsigned(a, q), addUnsigned(x, t)), s), b);
  const ff = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) =>
    cmn((b & c) | (~b & d), a, b, x, s, t);
  const gg = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) =>
    cmn((b & d) | (c & ~d), a, b, x, s, t);
  const hh = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) =>
    cmn(b ^ c ^ d, a, b, x, s, t);
  const ii = (a: number, b: number, c: number, d: number, x: number, s: number, t: number) =>
    cmn(c ^ (b | ~d), a, b, x, s, t);

  // UTF-8 encode
  const utf8 = unescape(encodeURIComponent(input));

  const x: number[] = [];
  const len = utf8.length;
  for (let i = 0; i < len; i++) x[i >> 2] = (x[i >> 2] || 0) | (utf8.charCodeAt(i) << ((i % 4) * 8));
  x[len >> 2] = (x[len >> 2] || 0) | (0x80 << ((len % 4) * 8));
  const bitLen = len * 8;
  const nBlocks = (((len + 8) >> 6) + 1) * 16;
  for (let i = 0; i < nBlocks; i++) if (x[i] === undefined) x[i] = 0;
  x[nBlocks - 2] = bitLen;

  let a = 0x67452301;
  let b = 0xefcdab89;
  let c = 0x98badcfe;
  let d = 0x10325476;

  for (let i = 0; i < nBlocks; i += 16) {
    const aa = a, bb = b, cc = c, dd = d;
    a = ff(a, b, c, d, x[i],     7,  -680876936);
    d = ff(d, a, b, c, x[i + 1], 12, -389564586);
    c = ff(c, d, a, b, x[i + 2], 17,  606105819);
    b = ff(b, c, d, a, x[i + 3], 22, -1044525330);
    a = ff(a, b, c, d, x[i + 4], 7,  -176418897);
    d = ff(d, a, b, c, x[i + 5], 12,  1200080426);
    c = ff(c, d, a, b, x[i + 6], 17, -1473231341);
    b = ff(b, c, d, a, x[i + 7], 22, -45705983);
    a = ff(a, b, c, d, x[i + 8], 7,   1770035416);
    d = ff(d, a, b, c, x[i + 9], 12, -1958414417);
    c = ff(c, d, a, b, x[i + 10], 17, -42063);
    b = ff(b, c, d, a, x[i + 11], 22, -1990404162);
    a = ff(a, b, c, d, x[i + 12], 7,   1804603682);
    d = ff(d, a, b, c, x[i + 13], 12, -40341101);
    c = ff(c, d, a, b, x[i + 14], 17, -1502002290);
    b = ff(b, c, d, a, x[i + 15], 22,  1236535329);

    a = gg(a, b, c, d, x[i + 1],  5,  -165796510);
    d = gg(d, a, b, c, x[i + 6],  9,  -1069501632);
    c = gg(c, d, a, b, x[i + 11], 14,  643717713);
    b = gg(b, c, d, a, x[i],      20, -373897302);
    a = gg(a, b, c, d, x[i + 5],  5,  -701558691);
    d = gg(d, a, b, c, x[i + 10], 9,   38016083);
    c = gg(c, d, a, b, x[i + 15], 14, -660478335);
    b = gg(b, c, d, a, x[i + 4],  20, -405537848);
    a = gg(a, b, c, d, x[i + 9],  5,   568446438);
    d = gg(d, a, b, c, x[i + 14], 9,  -1019803690);
    c = gg(c, d, a, b, x[i + 3],  14, -187363961);
    b = gg(b, c, d, a, x[i + 8],  20,  1163531501);
    a = gg(a, b, c, d, x[i + 13], 5,  -1444681467);
    d = gg(d, a, b, c, x[i + 2],  9,  -51403784);
    c = gg(c, d, a, b, x[i + 7],  14,  1735328473);
    b = gg(b, c, d, a, x[i + 12], 20, -1926607734);

    a = hh(a, b, c, d, x[i + 5],  4,  -378558);
    d = hh(d, a, b, c, x[i + 8],  11, -2022574463);
    c = hh(c, d, a, b, x[i + 11], 16,  1839030562);
    b = hh(b, c, d, a, x[i + 14], 23, -35309556);
    a = hh(a, b, c, d, x[i + 1],  4,  -1530992060);
    d = hh(d, a, b, c, x[i + 4],  11,  1272893353);
    c = hh(c, d, a, b, x[i + 7],  16, -155497632);
    b = hh(b, c, d, a, x[i + 10], 23, -1094730640);
    a = hh(a, b, c, d, x[i + 13], 4,   681279174);
    d = hh(d, a, b, c, x[i],      11, -358537222);
    c = hh(c, d, a, b, x[i + 3],  16, -722521979);
    b = hh(b, c, d, a, x[i + 6],  23,  76029189);
    a = hh(a, b, c, d, x[i + 9],  4,  -640364487);
    d = hh(d, a, b, c, x[i + 12], 11, -421815835);
    c = hh(c, d, a, b, x[i + 15], 16,  530742520);
    b = hh(b, c, d, a, x[i + 2],  23, -995338651);

    a = ii(a, b, c, d, x[i],      6,  -198630844);
    d = ii(d, a, b, c, x[i + 7],  10,  1126891415);
    c = ii(c, d, a, b, x[i + 14], 15, -1416354905);
    b = ii(b, c, d, a, x[i + 5],  21, -57434055);
    a = ii(a, b, c, d, x[i + 12], 6,   1700485571);
    d = ii(d, a, b, c, x[i + 3],  10, -1894986606);
    c = ii(c, d, a, b, x[i + 10], 15, -1051523);
    b = ii(b, c, d, a, x[i + 1],  21, -2054922799);
    a = ii(a, b, c, d, x[i + 8],  6,   1873313359);
    d = ii(d, a, b, c, x[i + 15], 10, -30611744);
    c = ii(c, d, a, b, x[i + 6],  15, -1560198380);
    b = ii(b, c, d, a, x[i + 13], 21,  1309151649);
    a = ii(a, b, c, d, x[i + 4],  6,  -145523070);
    d = ii(d, a, b, c, x[i + 11], 10, -1120210379);
    c = ii(c, d, a, b, x[i + 2],  15,  718787259);
    b = ii(b, c, d, a, x[i + 9],  21, -343485551);

    a = addUnsigned(a, aa);
    b = addUnsigned(b, bb);
    c = addUnsigned(c, cc);
    d = addUnsigned(d, dd);
  }
  return rhex(a) + rhex(b) + rhex(c) + rhex(d);
}

export type GravatarDefault = '404' | 'mp' | 'identicon' | 'monsterid' | 'wavatar' | 'retro' | 'robohash' | 'blank';

export interface GravatarOptions {
  size?: number;                // pixels (1..2048)
  defaultStyle?: GravatarDefault;
}

/** Build a Gravatar URL from an email address. */
export function gravatarUrl(email: string | null | undefined, opts: GravatarOptions = {}): string | undefined {
  if (!email) return undefined;
  const normalized = email.trim().toLowerCase();
  if (!normalized) return undefined;
  const hash = md5(normalized);
  const qs = new URLSearchParams();
  if (opts.size) qs.set('s', String(opts.size));
  qs.set('d', opts.defaultStyle ?? 'identicon');
  return `${GRAVATAR_ENDPOINT}${hash}?${qs.toString()}`;
}

/**
 * Resolve the best avatar URL to use in the UI.
 *
 * Priority:
 *   1. `explicitUrl` when non-empty (typically from the OAuth IdP).
 *   2. Gravatar computed from `email`.
 *   3. `undefined` — the consumer should show a fallback icon.
 */
export function resolveAvatar(
  explicitUrl: string | null | undefined,
  email: string | null | undefined,
  opts: GravatarOptions = {},
): string | undefined {
  if (explicitUrl && explicitUrl.trim()) return explicitUrl;
  return gravatarUrl(email, opts);
}
