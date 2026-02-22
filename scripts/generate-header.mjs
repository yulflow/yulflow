import { writeFileSync, mkdirSync } from "fs";

function seededRandom(seed) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

const rand = seededRandom(42);
const NUM_BARS = 100;
const SVG_WIDTH = 840;
const SVG_HEIGHT = 220;
const BAR_WIDTH = 2.8;
const MAX_BAR_HEIGHT = 90;
const BAR_Y = 185;

const bars = [];
for (let i = 0; i < NUM_BARS; i++) {
  const t = i / (NUM_BARS - 1);
  const bell = Math.exp(-Math.pow((t - 0.5) * 3.2, 2));
  const rhythm = 0.5 + 0.5 * Math.sin(t * Math.PI * 14);
  const noise = 0.35 + 0.65 * rand();
  const height = Math.max(5, Math.floor(MAX_BAR_HEIGHT * bell * rhythm * noise));
  const gap = (SVG_WIDTH - NUM_BARS * BAR_WIDTH) / (NUM_BARS + 1);
  const x = gap + i * (BAR_WIDTH + gap);
  bars.push({ x, height });
}

function createSVG(theme) {
  const isDark = theme === "dark";
  const textColor = isDark ? "#e6edf3" : "#1f2328";
  const subtitleColor = isDark ? "#7d8590" : "#656d76";
  const color1 = isDark ? "#58a6ff" : "#0969da";
  const color2 = isDark ? "#bc8cff" : "#8250df";

  // Two layers: background glow + foreground bars
  const glowBars = bars
    .map(
      ({ x, height }) =>
        `    <rect x="${(x - 1).toFixed(1)}" y="${BAR_Y - height - 2}" width="${BAR_WIDTH + 2}" height="${height + 4}" fill="url(#waveGrad)" rx="2" opacity="0.08"/>`
    )
    .join("\n");

  const mainBars = bars
    .map(
      ({ x, height }) =>
        `    <rect x="${x.toFixed(1)}" y="${BAR_Y - height}" width="${BAR_WIDTH}" height="${height}" fill="url(#waveGrad)" rx="1.4" opacity="0.4"/>`
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

  <!-- Glow layer -->
  <g>
${glowBars}
  </g>

  <!-- Main bars -->
  <g>
${mainBars}
  </g>

  <!-- Name -->
  <text x="${SVG_WIDTH / 2}" y="75" text-anchor="middle" fill="${textColor}"
    font-family="'SF Mono','Fira Code','Cascadia Code',monospace" font-size="38" font-weight="700" letter-spacing="8">
    SEOYUL SON
  </text>

  <!-- Subtitle -->
  <text x="${SVG_WIDTH / 2}" y="112" text-anchor="middle" fill="${subtitleColor}"
    font-family="'SF Mono','Fira Code','Cascadia Code',monospace" font-size="13" letter-spacing="4">
    MUSICIAN × AI DEVELOPER
  </text>
</svg>`;
}

mkdirSync("assets", { recursive: true });
writeFileSync("assets/header-dark.svg", createSVG("dark"));
writeFileSync("assets/header-light.svg", createSVG("light"));
console.log("Generated header SVGs");
