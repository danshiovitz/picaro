const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..', '..');
const clientRoot = path.join(root, 'client');
const esbuildBin = path.join(root, 'node_modules', 'esbuild', 'bin', 'esbuild');
const devServer = path.join(__dirname, 'dev-server.js');

const buildArgs = [
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
];

const distDir = path.join(clientRoot, 'dist');
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

const initial = spawnSync(esbuildBin, buildArgs, { cwd: clientRoot, stdio: 'inherit' });
if ((initial.status ?? 1) !== 0) process.exit(initial.status ?? 1);

const watcher = spawn(esbuildBin, [...buildArgs, '--watch=forever'], {
  cwd: clientRoot,
  stdio: 'inherit',
});
const server = spawn(process.execPath, [devServer], {
  cwd: clientRoot,
  stdio: 'inherit',
});

const shutdown = () => {
  watcher.kill('SIGINT');
  server.kill('SIGINT');
};

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
watcher.on('exit', (code) => {
  if (code && code !== 0) {
    server.kill('SIGINT');
    process.exitCode = code;
  }
});
server.on('exit', (code) => {
  if (code && code !== 0) {
    watcher.kill('SIGINT');
    process.exitCode = code;
  }
});
