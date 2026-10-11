const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..', '..');
const clientRoot = path.join(root, 'client');
const distDir = path.join(clientRoot, 'dist');
const esbuildBin = path.join(root, 'node_modules', 'esbuild', 'bin', 'esbuild');

fs.rmSync(distDir, { recursive: true, force: true });
fs.mkdirSync(distDir, { recursive: true });

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
    return;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

copyRecursive(path.join(clientRoot, 'index.html'), path.join(distDir, 'index.html'));
copyRecursive(path.join(clientRoot, 'src', 'style.css'), path.join(distDir, 'style.css'));

const result = spawnSync(
  esbuildBin,
  [
    path.join(clientRoot, 'src', 'main.ts'),
    '--bundle',
    '--format=esm',
    '--target=es2022',
    '--outdir=dist',
    '--sourcemap',
    '--public-path=/',
    '--loader:.svg=file',
    '--loader:.png=file',
    '--loader:.jpg=file',
    '--loader:.jpeg=file',
    '--loader:.gif=file',
    '--loader:.webp=file',
    '--define:import.meta.env.VITE_API_URL=""',
  ],
  { cwd: clientRoot, stdio: 'inherit' },
);

process.exit(result.status ?? 1);
