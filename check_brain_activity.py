#!/usr/bin/env python3
"""
Check why brain isn't making changes
"""

# Read the log and find brain's responses
with open('autonomous_daemon.log', 'r') as f:
    lines = f.readlines()

# Find the self-assessment responses
in_assessment = False
assessment_lines = []

for i, line in enumerate(lines):
    if "Brain's self-assessment:" in line:
        # Get the next few lines to see the full response
        assessment_lines.append("\n" + "="*60)
        assessment_lines.append(line.strip())
        for j in range(i+1, min(i+10, len(lines))):
            if "INFO" in lines[j] and ("Brain" in lines[j] or "needs" in lines[j] or "goals" in lines[j]):
                assessment_lines.append(lines[j].strip())
                if "identified" in lines[j]:
                    break

print("\n🔍 Brain's Self-Assessments:\n")
for line in assessment_lines[-50:]:  # Last 50 relevant lines
    print(line)

# Check for needs identified
print("\n" + "="*60)
print("📊 Needs Identification Summary:")
print("="*60)

needs_count = {}
for line in lines:
    if "Brain identified" in line and "needs" in line:
        if "0 needs" in line:
            needs_count["0 needs"] = needs_count.get("0 needs", 0) + 1
        else:
            # Extract number
            import re
            match = re.search(r'identified (\d+) needs', line)
            if match:
                count = match.group(1)
                needs_count[f"{count} needs"] = needs_count.get(f"{count} needs", 0) + 1

for key, count in needs_count.items():
    print(f"  • {key}: {count} times")

print("\n" + "="*60)
print("🎯 Goal Execution Summary:")
print("="*60)

for line in lines:
    if "executing" in line.lower() and "goals" in line.lower():
        print(f"  {line.strip()}")
