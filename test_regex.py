
import re

# 测试正则表达式
pat = re.compile(r'[「『"'']([^」』"'']{2,10})[」』"'']')
desc = '「没事」'
m = pat.search(desc)
print(f'匹配结果: {m}')
if m:
    print(f'提取的关键词: {m.group(1)}')
