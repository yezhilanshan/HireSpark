// Generates PNG PWA icons from the SVG icon
// Run: node scripts/generate-icons.cjs

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const ICONS_DIR = path.join(PUBLIC_DIR, 'icons');

if (!fs.existsSync(ICONS_DIR)) {
  fs.mkdirSync(ICONS_DIR, { recursive: true });
}

// Check if sharp is available, offer fallback
try {
  require.resolve('sharp');
} catch {
  console.log('[icons] sharp not installed. Installing...');
  execSync('npm install --save-dev sharp', { stdio: 'inherit', cwd: path.join(__dirname, '..') });
}

const sharp = require('sharp');
const svgBuffer = fs.readFileSync(path.join(PUBLIC_DIR, 'icon.svg'));

async function generate() {
  // 192x192 (primary icon + apple touch icon)
  await sharp(svgBuffer).resize(192, 192).png().toFile(path.join(ICONS_DIR, 'icon-192.png'));
  console.log('✓ icon-192.png');

  // 512x512 (large icon + splash screen)
  await sharp(svgBuffer).resize(512, 512).png().toFile(path.join(ICONS_DIR, 'icon-512.png'));
  console.log('✓ icon-512.png');

  // 512x512 maskable (with padding for adaptive icons)
  const maskableSvg = svgBuffer.toString('utf-8')
    .replace('<svg ', '<svg width="512" height="512" ');
  await sharp(Buffer.from(maskableSvg)).resize(512, 512, { fit: 'contain', background: '#0f172a' }).png().toFile(path.join(ICONS_DIR, 'icon-512-maskable.png'));
  console.log('✓ icon-512-maskable.png');

  // 180x180 (iOS apple-touch-icon specific)
  await sharp(svgBuffer).resize(180, 180).png().toFile(path.join(ICONS_DIR, 'apple-touch-icon.png'));
  console.log('✓ apple-touch-icon.png');

  console.log('\nAll PWA icons generated in public/icons/');
}

generate().catch((err) => {
  console.error('Icon generation failed:', err.message);
  process.exit(1);
});
