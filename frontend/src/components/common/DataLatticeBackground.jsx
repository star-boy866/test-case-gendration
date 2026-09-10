import React from "react";

/**
 * DataLatticeBackground
 * 
 * Minimal, elegant, and visible animated "data flow" background for the DSD Upload page.
 * Features 3–4 thin flowing SVG paths with subtle stroke-dash animation,
 * 15 strategically positioned nodes (with soft-glowing highlight nodes),
 * and 3 very faint ambient radial gradient glows in the outer margins.
 * 
 * Target visual weight: 15–20% visibility (clearly noticeable, yet never competing with the DSD card).
 * Strictly pointer-events: none and respects prefers-reduced-motion.
 */
export default function DataLatticeBackground() {
  return (
    <div 
      className="pointer-events-none absolute inset-0 w-full h-full overflow-hidden z-0 select-none"
      aria-hidden="true"
    >
      {/* ── Soft Ambient Radial Glows in Margins ── */}
      <div 
        className="absolute -top-16 -left-16 w-[460px] h-[460px] rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.11)_0%,rgba(59,130,246,0)_70%)] animate-glow-bloom" 
      />
      <div 
        className="absolute -top-12 -right-12 w-[500px] h-[500px] rounded-full bg-[radial-gradient(circle,rgba(99,102,241,0.09)_0%,rgba(99,102,241,0)_70%)] animate-glow-bloom"
        style={{ animationDelay: "-4s" }}
      />
      <div 
        className="absolute -bottom-24 right-1/4 w-[480px] h-[480px] rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.10)_0%,rgba(59,130,246,0)_70%)] animate-glow-bloom"
        style={{ animationDelay: "-8s" }}
      />

      {/* ── Flowing Data Lattice SVG ── */}
      <svg 
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1440 900" 
        fill="none" 
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id="flowGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.14" />
            <stop offset="50%" stopColor="#2563eb" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.15" />
          </linearGradient>
          <linearGradient id="flowGrad2" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.18" />
            <stop offset="60%" stopColor="#4f46e5" stopOpacity="0.16" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.12" />
          </linearGradient>
          <linearGradient id="flowGrad3" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.14" />
            <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0.16" />
          </linearGradient>
          <linearGradient id="flowGrad4" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.12" />
          </linearGradient>
        </defs>

        {/* ── Secondary Cross-Connecting Link Segments ── */}
        <g stroke="rgba(59, 130, 246, 0.12)" strokeWidth="1" strokeDasharray="4 6" className="hidden sm:inline">
          <line x1="180" y1="88" x2="130" y2="250" />
          <line x1="1280" y1="105" x2="1335" y2="215" />
          <line x1="1210" y1="860" x2="1340" y2="610" />
          <line x1="260" y1="840" x2="160" y2="560" />
        </g>

        {/* ── 1. Upper Flow Path (Top Margin) ── */}
        <path 
          d="M -40,110 C 260,65 520,135 840,85 C 1120,40 1320,140 1480,115" 
          stroke="url(#flowGrad1)" 
          strokeWidth="1.5" 
          strokeLinecap="round"
          className="animate-flow-dash-1"
        />

        {/* ── 2. Left Flank Path (Left Margin) ── */}
        <path 
          d="M -30,280 C 140,240 210,420 160,560 C 110,700 180,810 360,845" 
          stroke="url(#flowGrad2)" 
          strokeWidth="1.5" 
          strokeLinecap="round"
          className="animate-flow-dash-2"
        />

        {/* ── 3. Lower Flow Path (Bottom Margin) ── */}
        <path 
          d="M 120,865 C 380,880 720,820 1020,855 C 1220,880 1360,760 1480,720" 
          stroke="url(#flowGrad3)" 
          strokeWidth="1.5" 
          strokeLinecap="round"
          className="animate-flow-dash-3"
        />

        {/* ── 4. Right Flank Path (Right Margin) ── */}
        <path 
          d="M 1480,240 C 1320,210 1260,390 1315,520 C 1365,630 1340,780 1210,860" 
          stroke="url(#flowGrad4)" 
          strokeWidth="1.25" 
          strokeLinecap="round"
          className="animate-flow-dash-4"
        />

        {/* ── Standard Nodes (4–5px, Opacity 0.32–0.42) ── */}
        <g fill="rgba(37, 99, 235, 0.38)">
          <circle cx="180" cy="88" r="4.5" />
          <circle cx="960" cy="72" r="4" />
          <circle cx="1280" cy="105" r="4.5" />
          <circle cx="130" cy="250" r="4" />
          <circle cx="140" cy="640" r="4" />
          <circle cx="260" cy="840" r="4.5" />
          <circle cx="480" cy="872" r="4" />
          <circle cx="1140" cy="860" r="4.5" />
          <circle cx="1360" cy="750" r="4" />
          <circle cx="1335" cy="215" r="4.5" />
          <circle cx="1340" cy="610" r="4" />
        </g>

        {/* ── Highlight / Important Nodes (7–9px Outer Glow + Core) ── */}
        {/* Highlight Node 1: Top Center */}
        <g>
          <circle 
            cx="520" 
            cy="115" 
            r="8.5" 
            fill="rgba(59, 130, 246, 0.14)" 
            stroke="rgba(37, 99, 235, 0.38)" 
            strokeWidth="1" 
            className="animate-node-pulse"
          />
          <circle cx="520" cy="115" r="4.5" fill="rgba(37, 99, 235, 0.60)" />
        </g>

        {/* Highlight Node 2: Left Flank */}
        <g>
          <circle 
            cx="180" 
            cy="480" 
            r="8.5" 
            fill="rgba(59, 130, 246, 0.14)" 
            stroke="rgba(37, 99, 235, 0.38)" 
            strokeWidth="1" 
            className="animate-node-pulse"
            style={{ animationDelay: "-2.5s" }}
          />
          <circle cx="180" cy="480" r="4.5" fill="rgba(37, 99, 235, 0.60)" />
        </g>

        {/* Highlight Node 3: Right Flank */}
        <g>
          <circle 
            cx="1280" 
            cy="440" 
            r="8.5" 
            fill="rgba(59, 130, 246, 0.14)" 
            stroke="rgba(37, 99, 235, 0.38)" 
            strokeWidth="1" 
            className="animate-node-pulse"
            style={{ animationDelay: "-5s" }}
          />
          <circle cx="1280" cy="440" r="4.5" fill="rgba(37, 99, 235, 0.60)" />
        </g>

        {/* Highlight Node 4: Bottom Center */}
        <g>
          <circle 
            cx="860" 
            cy="840" 
            r="8.5" 
            fill="rgba(59, 130, 246, 0.14)" 
            stroke="rgba(37, 99, 235, 0.38)" 
            strokeWidth="1" 
            className="animate-node-pulse"
            style={{ animationDelay: "-7.5s" }}
          />
          <circle cx="860" cy="840" r="4.5" fill="rgba(37, 99, 235, 0.60)" />
        </g>
      </svg>
    </div>
  );
}
