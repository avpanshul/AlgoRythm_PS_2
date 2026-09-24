import os
import re

dir_path = '/Users/divvyas/PS156/frontend/src'

color_map = {
    # Text Primary
    r'#e2e8f0': 'var(--color-text-primary)',
    r'#cbd5e1': 'var(--color-text-primary)',
    r'#ffffff': 'var(--color-bg-primary)', # if someone used white text expecting a dark bg
    r'"white"': '"var(--color-bg-primary)"',
    r"'white'": "'var(--color-bg-primary)'",
    
    # Text Muted
    r'#94a3b8': 'var(--color-text-muted)',
    r'#64748b': 'var(--color-text-muted)',
    r'#475569': 'var(--color-text-muted)',
    
    # Borders / Darker
    r'#334155': 'var(--color-border)',
    r'#1e2842': 'var(--color-border)',
    
    # Backgrounds
    r'#0f1525': 'var(--color-bg-secondary)',
    r'#141928': 'var(--color-bg-card)',
    r'#0a0e1a': 'var(--color-bg-primary)',
    r'rgba\(20,25,40,[^\)]+\)': 'var(--color-bg-card)',
    r'rgba\(20, 25, 40,[^\)]+\)': 'var(--color-bg-card)',
    r'rgba\(30,40,66,[^\)]+\)': 'var(--color-border)',
    r'rgba\(30, 40, 66,[^\)]+\)': 'var(--color-border)',
    
    # Accent colors that might be hard to read or look neon
    r'#60a5fa': 'var(--color-text-primary)', # light blue -> primary text
    r'#38bdf8': 'var(--color-text-primary)',
    r'#a78bfa': 'var(--color-text-primary)',
    r'#a5b4fc': 'var(--color-text-primary)',
    r'#34d399': 'var(--color-success)',
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
        if file.endswith('.tsx') or file.endswith('.ts'):
            process_file(os.path.join(root, file))

print("Color replacement complete.")
