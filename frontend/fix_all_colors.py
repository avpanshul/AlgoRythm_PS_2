import os
import re

dir_path = '/Users/divvyas/PS156/frontend/src'

color_map = {
    # Light Grays
    r'#e2e8f0': 'var(--color-text-primary)',
    r'#cbd5e1': 'var(--color-text-primary)',
    r'#94a3b8': 'var(--color-text-primary)',
    r'#64748b': 'var(--color-text-muted)',
    r'#475569': 'var(--color-text-muted)',
    
    # Blues, Purples, Indigos (User wants no blue highlights)
    r'#0ea5e9': 'var(--color-text-primary)',
    r'#8b5cf6': 'var(--color-text-primary)',
    r'#3b82f6': 'var(--color-text-primary)',
    r'#6366f1': 'var(--color-text-primary)',
    r'#60a5fa': 'var(--color-text-primary)',
    r'#a78bfa': 'var(--color-text-primary)',
    r'#38bdf8': 'var(--color-text-primary)',
    r'#a5b4fc': 'var(--color-text-primary)',
    
    # Backgrounds/Borders
    r'#0f1525': 'var(--color-bg-primary)',
    r'#141928': 'var(--color-bg-primary)',
    r'#0a0e1a': 'var(--color-bg-primary)',
    r'#1e2842': 'var(--color-border)',
    r'#334155': 'var(--color-border)',
    r'#060b14': 'var(--color-bg-primary)',
    
    # RGBA background variations (Remove them by making them transparent or white)
    r'rgba\(\d+,\s*\d+,\s*\d+,\s*0\.\d+\)': 'transparent',
    
    # Specific edge case: white text
    r'color:\s*["\']white["\']': 'color: "var(--color-text-primary)"',
    r'color="white"': 'color="var(--color-text-primary)"',
}

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    new_content = content
    for pattern, replacement in color_map.items():
        new_content = re.sub(pattern, replacement, new_content, flags=re.IGNORECASE)
        
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Fixed {filepath}")

for root, _, files in os.walk(dir_path):
    for file in files:
        if file.endswith('.tsx') or file.endswith('.ts') or file.endswith('.css'):
            process_file(os.path.join(root, file))

print("All colors fixed.")
