import { RNG } from "./random.js";
export class PerlinNoise {
  perm;
  constructor(seed) {
    const rng = new RNG(seed);
    const p = [...Array(256).keys()];
    for (let i = p.length - 1; i > 0; i--) {
      const j = rng.int(i + 1);
      [p[i], p[j]] = [p[j], p[i]];
    }
    this.perm = [...p, ...p];
  }
  fade(t) {
    return t * t * t * (t * (t * 6 - 15) + 10);
  }
  lerp(a, b, t) {
    return a + t * (b - a);
  }
  grad(hash, x, y) {
    switch (hash & 3) {
      case 0:
        return x + y;
      case 1:
        return -x + y;
      case 2:
        return x - y;
      default:
        return -x - y;
    }
  }
  noise(x, y) {
    const xi = Math.floor(x) & 255;
    const yi = Math.floor(y) & 255;
    const xf = x - Math.floor(x);
    const yf = y - Math.floor(y);
    const u = this.fade(xf);
    const v = this.fade(yf);
    const aa = this.perm[this.perm[xi] + yi];
    const ab = this.perm[this.perm[xi] + yi + 1];
    const ba = this.perm[this.perm[xi + 1] + yi];
    const bb = this.perm[this.perm[xi + 1] + yi + 1];
    const x1 = this.lerp(this.grad(aa, xf, yf), this.grad(ba, xf - 1, yf), u);
    const x2 = this.lerp(
      this.grad(ab, xf, yf - 1),
      this.grad(bb, xf - 1, yf - 1),
      u,
    );
    return (this.lerp(x1, x2, v) + 1) / 2;
  }
}
export function noiseValue(noise, x, y, scale, octaves = 4) {
  let value = 0;
  let amplitude = 0.5;
  let frequency = 2;
  let totalAmplitude = 0;
  for (let i = 0; i < octaves; i++) {
    value +=
      noise.noise(x * scale * frequency, y * scale * frequency) * amplitude;
    totalAmplitude += amplitude;
    amplitude *= 0.5;
    frequency *= 2;
  }
  return value / totalAmplitude;
}
