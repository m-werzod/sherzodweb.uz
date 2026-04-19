/**
 * Compresses all PNG/JPG images in public/ to optimized WebP
 * Run: node scripts/compress-images.mjs
 */
import sharp from 'sharp'
import { readdirSync, statSync, mkdirSync } from 'fs'
import { join, extname, basename, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PUBLIC   = join(__dirname, '../public')

const TARGETS = [
  { src: 'images/hero2.png',              dest: 'images/hero2.webp',              width: 760  },
  { src: 'images/projects/ecommerce.png', dest: 'images/projects/ecommerce.webp', width: 800  },
  { src: 'images/projects/restaurant.png',dest: 'images/projects/restaurant.webp',width: 800  },
  { src: 'images/projects/educrm.png',    dest: 'images/projects/educrm.webp',    width: 800  },
  { src: 'images/about.png',              dest: 'images/about.webp',              width: 600  },
]

for (const { src, dest, width } of TARGETS) {
  const srcPath  = join(PUBLIC, src)
  const destPath = join(PUBLIC, dest)
  try {
    const info = await sharp(srcPath)
      .resize(width, null, { withoutEnlargement: true })
      .webp({ quality: 82, effort: 6 })
      .toFile(destPath)
    const origSize = statSync(srcPath).size
    console.log(`✅ ${src} → ${dest}  (${(origSize/1024).toFixed(0)} KB → ${(info.size/1024).toFixed(0)} KB, saved ${(100-(info.size/origSize*100)).toFixed(0)}%)`)
  } catch (e) {
    console.error(`❌ ${src}: ${e.message}`)
  }
}
console.log('\nDone.')
