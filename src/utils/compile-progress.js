/**
 * Compile Progress Tracker
 * Parses GCC/compiler output into recognizable compile steps
 */

const COMPILE_STEPS = [
  { pattern: /loading|recipepreprocessing|preparing/, label: 'Preparing', icon: '⚙' },
  { pattern: /platform/, label: 'Loading platform', icon: '📦' },
  { pattern: /compiling.*core|archivecore|archive\.a/, label: 'Compiling core', icon: '⚡' },
  { pattern: /compiling.*sketch|\.ino/, label: 'Compiling sketch', icon: '📝' },
  { pattern: /linking|\.o:|combining|Recipe for target/, label: 'Linking', icon: '🔗' },
  { pattern: /generating|hexdump|size report|bytes of|Memory usage/, label: 'Finalizing', icon: '✨' },
];

export function parseCompileProgress(output) {
  const lines = output.split('\n');
  const steps = new Map(); // Map of step name -> { started, completed, lines }
  
  lines.forEach((line, idx) => {
    const trimmed = line.toLowerCase();
    
    // Find matching step
    for (const step of COMPILE_STEPS) {
      if (step.pattern.test(trimmed)) {
        if (!steps.has(step.label)) {
          steps.set(step.label, { 
            icon: step.icon,
            started: idx,
            completed: false,
            lines: []
          });
        }
        steps.get(step.label).lines.push(line);
        break;
      }
    }
  });

  // Mark last step as completed
  if (steps.size > 0) {
    const lastStep = Array.from(steps.values()).pop();
    lastStep.completed = true;
  }

  return Array.from(steps.entries()).map(([label, data]) => ({
    label,
    icon: data.icon,
    started: data.started >= 0,
    completed: data.completed,
    lineCount: data.lines.length,
  }));
}

export function detectCompileError(output) {
  const lines = output.split('\n');
  
  for (const line of lines) {
    if (line.includes('error:') || line.includes('undefined reference')) {
      return { hasError: true, line };
    }
  }
  
  return { hasError: false };
}

export function getProgressPercentage(steps) {
  if (steps.length === 0) return 0;
  const completedSteps = steps.filter(s => s.completed).length;
  return Math.round((completedSteps / steps.length) * 100);
}
