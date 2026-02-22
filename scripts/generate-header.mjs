import { writeFileSync, mkdirSync } from "fs";

function seededRandom(seed) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

const rand = seededRandom(42);
const NUM_BARS = 120;
const SVG_WIDTH = 840;
const SVG_HEIGHT = 160;
const BAR_WIDTH = 2.4;
const MAX_BAR_HEIGHT = 110;
const BAR_Y = 145;

const bars = [];
for (let i = 0; i < NUM_BARS; i++) {
  const t = i / (NUM_BARS - 1);
  const bell = Math.exp(-Math.pow((t - 0.5) * 2.8, 2));
  const rhythm = 0.5 + 0.5 * Math.sin(t * Math.PI * 16);
  const noise = 0.3 + 0.7 * rand();
  const height = Math.max(4, Math.floor(MAX_BAR_HEIGHT * bell * rhythm * noise));
  const gap = (SVG_WIDTH - NUM_BARS * BAR_WIDTH) / (NUM_BARS + 1);
  const x = gap + i * (BAR_WIDTH + gap);
  bars.push({ x, height });
}

function createSVG(theme) {
  const isDark = theme === "dark";
  const handleColor = isDark ? "#484f58" : "#b1bac4";
  const color1 = isDark ? "#58a6ff" : "#0969da";
  const color2 = isDark ? "#bc8cff" : "#8250df";

  const glowBars = bars
    .map(
      ({ x, height }) =>
        `    <rect x="${(x - 1.5).toFixed(1)}" y="${BAR_Y - height - 3}" width="${BAR_WIDTH + 3}" height="${height + 6}" fill="url(#waveGrad)" rx="2.5" opacity="0.06"/>`
    )
    .join("\n");

  const mainBars = bars
    .map(
      ({ x, height }) =>
        `    <rect x="${x.toFixed(1)}" y="${BAR_Y - height}" width="${BAR_WIDTH}" height="${height}" fill="url(#waveGrad)" rx="1.2" opacity="0.45"/>`
    )
    .join("\n");

  return `<svg width="${SVG_WIDTH}" height="${SVG_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="waveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="${color1}"/>
      <stop offset="50%" stop-color="${color2}"/>
      <stop offset="100%" stop-color="${color1}"/>
    </linearGradient>
  </defs>

  <!-- Glow -->
  <g>
${glowBars}
  </g>

  <!-- Bars -->
  <g>
${mainBars}
  </g>

  <!-- Handle -->
  <text x="${SVG_WIDTH / 2}" y="${SVG_HEIGHT - 4}" text-anchor="middle" fill="${handleColor}"
    font-family="'SF Mono','Fira Code','Cascadia Code',monospace" font-size="11" letter-spacing="3">
    yulflow
  </text>
</svg>`;
}

mkdirSync("assets", { recursive: true });
writeFileSync("assets/header-dark.svg", createSVG("dark"));
writeFileSync("assets/header-light.svg", createSVG("light"));
console.log("Generated header SVGs");
