"""
Phân tích CẤU TRÚC JSON của output.zip (chuẩn) để tìm quy luật
"""

import zipfile
import json
import re

print("="*80)
print("🔍 PHÂN TÍCH CẤU TRÚC JSON CHUẨN (output.zip)")
print("="*80)

z_standard = zipfile.ZipFile('output.zip', 'r')
z_submit = zipfile.ZipFile('submission.zip', 'r')

# Đọc raw text để kiểm tra format
standard_text = z_standard.read('output/EC_001.json').decode('utf-8')
submit_text = z_submit.read('output/EC_001.json').decode('utf-8')

print("\n📋 RAW TEXT COMPARISON (first 500 chars):")
print("\n--- output.zip (CHUẨN) ---")
print(repr(standard_text[:500]))
print("\n--- submission.zip ---")
print(repr(submit_text[:500]))

# Phân tích indent
print("\n" + "="*80)
print("🔍 PHÂN TÍCH CHI TIẾT:")
print("="*80)

# 1. Line endings
print("\n1️⃣ LINE ENDINGS:")
has_crlf_std = '\r\n' in standard_text
has_crlf_sub = '\r\n' in submit_text
std_type = 'CRLF (\\r\\n)' if has_crlf_std else 'LF (\\n)'
sub_type = 'CRLF (\\r\\n)' if has_crlf_sub else 'LF (\\n)'
print(f"   output.zip: {std_type}")
print(f"   submission.zip: {sub_type}")
if has_crlf_std != has_crlf_sub:
    correct_type = 'CRLF' if has_crlf_std else 'LF'
    print(f"   ❌ KHÁC NHAU! Phải dùng: {correct_type}")

# 2. Indent style
print("\n2️⃣ INDENT:")
lines_std = standard_text.split('\n' if not has_crlf_std else '\r\n')
lines_sub = submit_text.split('\n' if not has_crlf_sub else '\r\n')

# Đếm spaces ở dòng đầu tiên có indent
for i, line in enumerate(lines_std[:10]):
    if line.startswith(' ') and '"' in line:
        spaces = len(line) - len(line.lstrip())
        print(f"   output.zip line {i}: {spaces} spaces - {repr(line[:50])}")
        break

for i, line in enumerate(lines_sub[:10]):
    if line.startswith(' ') and '"' in line:
        spaces = len(line) - len(line.lstrip())
        print(f"   submission.zip line {i}: {spaces} spaces - {repr(line[:50])}")
        break

# 3. Key order
print("\n3️⃣ KEY ORDER:")
std_json = json.loads(standard_text)
sub_json = json.loads(submit_text)

# Parse lại để lấy thứ tự key trong raw text
std_keys = []
for line in lines_std:
    match = re.search(r'^\s*"([^"]+)":', line)
    if match and '{' not in line and match.group(1) != '':
        std_keys.append(match.group(1))

sub_keys = []
for line in lines_sub:
    match = re.search(r'^\s*"([^"]+)":', line)
    if match and '{' not in line and match.group(1) != '':
        sub_keys.append(match.group(1))

print(f"   output.zip key order (first 15): {std_keys[:15]}")
print(f"   submission.zip key order (first 15): {sub_keys[:15]}")

if std_keys[:15] != sub_keys[:15]:
    print(f"   ❌ THỨ TỰ KEY KHÁC NHAU!")
    for i, (k1, k2) in enumerate(zip(std_keys[:15], sub_keys[:15])):
        if k1 != k2:
            print(f"      Position {i}: output={k1}, submission={k2}")

# 4. Trailing newline
print("\n4️⃣ TRAILING NEWLINE:")
print(f"   output.zip ends with: {repr(standard_text[-10:])}")
print(f"   submission.zip ends with: {repr(submit_text[-10:])}")
if standard_text.endswith('\n') != submit_text.endswith('\n'):
    has_newline = 'có' if standard_text.endswith('\n') else 'không'
    print(f"   ❌ KHÁC! output.zip {has_newline} newline cuối file")

# 5. So sánh nhiều file để tìm pattern
print("\n5️⃣ PATTERN ANALYSIS (kiểm tra 5 files):")
for case_id in ['EC_001', 'EC_002', 'EC_010', 'EC_012', 'EC_025']:
    std = z_standard.read(f'output/{case_id}.json').decode('utf-8')
    sub = z_submit.read(f'output/{case_id}.json').decode('utf-8')
    
    same_structure = (
        (('\r\n' in std) == ('\r\n' in sub)) and
        (std.endswith('\n') == sub.endswith('\n'))
    )
    
    print(f"   {case_id}: {'✅' if same_structure else '❌'} {'Same' if same_structure else 'Different'}")

print("\n" + "="*80)
print("💡 KẾT LUẬN:")
print("="*80)

print("""
Để output khớp với output.zip (chuẩn), cần:
1. Line endings: LF (\\n) nếu output.zip dùng LF, CRLF (\\r\\n) nếu dùng CRLF
2. Indent: Giống output.zip (có thể 2 hoặc 4 spaces)
3. Key order: Phải giống CHÍNH XÁC thứ tự trong output.zip
4. Trailing newline: Có hoặc không theo output.zip
5. JSON.dumps parameters cần match với output.zip
""")

print("="*80)

z_standard.close()
z_submit.close()
