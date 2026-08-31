import React from "react";

/**
 * DriftingParticles
 * 
 * Lightweight, accessible ambient particle layer.
 * Renders 8 tiny floating circular particles with gentle drift animations.
 * Uses very low opacity and pure CSS translate displacement to remain completely unobtrusive.
 * Automatically disabled when prefers-reduced-motion is active.
 */
export default function DriftingParticles() {
  return (
    <div 
      className="pointer-events-none absolute inset-0 overflow-hidden z-0" 
      aria-hidden="true"
    >
      {/* Particle 1: Blue - Top Left */}
      <div 
        className="absolute top-[8%] left-[10%] w-2 h-2 rounded-full bg-blue-500/20 particle-drift-1" 
        style={{ filter: "blur(0.5px)" }}
      />
      {/* Particle 2: Indigo - Top Right */}
      <div 
        className="absolute top-[18%] left-[82%] w-2.5 h-2.5 rounded-full bg-indigo-500/20 particle-drift-2" 
        style={{ filter: "blur(0.5px)" }}
      />
      {/* Particle 3: Sky - Center Left */}
      <div 
        className="absolute top-[42%] left-[28%] w-1.5 h-1.5 rounded-full bg-sky-500/20 particle-drift-3" 
      />
      {/* Particle 4: Blue - Center Right */}
      <div 
        className="absolute top-[55%] left-[88%] w-3 h-3 rounded-full bg-blue-600/15 particle-drift-4" 
        style={{ filter: "blur(0.5px)" }}
      />
      {/* Particle 5: Indigo - Bottom Left */}
      <div 
        className="absolute top-[78%] left-[15%] w-2 h-2 rounded-full bg-indigo-400/20 particle-drift-5" 
      />
      {/* Particle 6: Sky - Far Left */}
      <div 
        className="absolute top-[32%] left-[4%] w-1.5 h-1.5 rounded-full bg-sky-600/15 particle-drift-6" 
      />
      {/* Particle 7: Indigo - Bottom Center */}
      <div 
        className="absolute top-[72%] left-[54%] w-2 h-2 rounded-full bg-indigo-500/15 particle-drift-7" 
      />
      {/* Particle 8: Blue - Top Center */}
      <div 
        className="absolute top-[12%] left-[50%] w-2.5 h-2.5 rounded-full bg-blue-400/20 particle-drift-8" 
        style={{ filter: "blur(0.5px)" }}
      />
    </div>
  );
}
