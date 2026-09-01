import os, glob

files = sorted(glob.glob('正文/第*章.txt'))
total_replaced = 0

for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    
    original = content
    
    # 替换连续双引号为标准中文引号
    # "" → "
    content = content.replace('\u201c\u201c', '\u201c')
    # "" → "  
    content = content.replace('\u201d\u201d', '\u201d')
    
    if content != original:
        with open(f, 'w', encoding='utf-8') as fh:
            fh.write(content)
        total_replaced += 1

print(f'引号替换完成：共修复 {total_replaced} 个文件')

# 验证
remaining = 0
for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    remaining += content.count('\u201c\u201c') + content.count('\u201d\u201d')
print(f'剩余连续双引号: {remaining} 处')
