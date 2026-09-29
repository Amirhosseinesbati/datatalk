import { readFileSync, readdirSync } from 'node:fs'

const root = new URL('../screenshots/', import.meta.url)
function jpegSize(bytes) {
  let offset = 2
  while (offset < bytes.length - 9) {
    if (bytes[offset] !== 0xff) { offset += 1; continue }
    const marker = bytes[offset + 1]
    offset += 2
    if (marker === 0xd9 || marker === 0xda) break
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue
    const length = bytes.readUInt16BE(offset)
    if (length < 2) break
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      return [bytes.readUInt16BE(offset + 5), bytes.readUInt16BE(offset + 3)]
    }
    offset += length
  }
  throw new Error('JPEG size marker not found')
}

for (const name of readdirSync(root).filter(name => /\.(png|jpe?g)$/i.test(name)).sort()) {
  const bytes = readFileSync(new URL(name, root))
  const png = bytes.toString('ascii', 1, 4) === 'PNG'
  const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8
  if (!png && !jpeg) throw new Error(`${name}: unsupported image signature`)
  const [width, height] = png ? [bytes.readUInt32BE(16), bytes.readUInt32BE(20)] : jpegSize(bytes)
  const format = png ? 'PNG' : 'JPEG'
  const extensionMatches = png ? name.toLowerCase().endsWith('.png') : /\.jpe?g$/i.test(name)
  process.stdout.write(`${name}\t${width}x${height}\t${format}${extensionMatches ? '' : ' · extension mismatch'}\n`)
}
