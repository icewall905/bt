// Generates PNG app icons from static/favicon.svg (run: npm run icons). Output is committed.
import sharp from 'sharp';
import { readFile, mkdir } from 'node:fs/promises';

const svg = await readFile(new URL('../static/favicon.svg', import.meta.url));
const out = new URL('../static/icons/', import.meta.url);
await mkdir(out, { recursive: true });

// Maskable: full-bleed background, artwork shrunk into the 80% safe zone.
const inner = await sharp(svg, { density: 384 }).resize(360, 360).png().toBuffer();
const maskable = sharp({ create: { width: 512, height: 512, channels: 4, background: '#17123a' } })
	.composite([{ input: inner, top: 76, left: 76 }]);

await Promise.all([
	sharp(svg, { density: 384 }).resize(192, 192).png().toFile(new URL('icon-192.png', out).pathname),
	sharp(svg, { density: 384 }).resize(512, 512).png().toFile(new URL('icon-512.png', out).pathname),
	sharp(svg, { density: 384 }).resize(180, 180).flatten({ background: '#0a0817' }).png().toFile(new URL('apple-touch-icon.png', out).pathname),
	maskable.png().toFile(new URL('maskable-512.png', out).pathname)
]);
console.log('icons written');
