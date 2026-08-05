"""
So sánh NỘI DUNG chi tiết giữa output.zip (chuẩn) và submission.zip
"""

import zipfile
import json

print("="*80)
print("🔍 SO SÁNH NỘI DUNG output.zip (CHUẨN) vs submission.zip")
print("="*80)

z_standard = zipfile.ZipFile('output.zip', 'r')
z_submit = zipfile.ZipFile('submission.zip', 'r')

# So sánh EC_001
print("\n📄 So sánh EC_001.json:")

standard = json.loads(z_standard.read('output/EC_001.json'))
submit = json.loads(z_submit.read('output/EC_001.json'))

print(f"\n🔑 Top-level keys:")
print(f"   output.zip: {list(standard.keys())}")
print(f"   submission.zip: {list(submit.keys())}")

if standard.keys() != submit.keys():
    print("\n❌ KHÁC TOP-LEVEL KEYS!")
    missing = set(standard.keys()) - set(submit.keys())
    extra = set(submit.keys()) - set(standard.keys())
    if missing:
        print(f"   Thiếu: {missing}")
    if extra:
        print(f"   Thừa: {extra}")
else:
    print("   ✅ Top-level keys giống nhau")

# So sánh từng section
print(f"\n🔍 Chi tiết từng section:")

for key in standard.keys():
    if standard.get(key) != submit.get(key):
        print(f"\n❌ Khác nhau ở '{key}':")
        print(f"   output.zip: {standard.get(key)}")
        print(f"   submission.zip: {submit.get(key)}")
    else:
        print(f"   ✅ {key}: giống nhau")

# So sánh byte-by-byte
print(f"\n🔬 So sánh byte-level:")
standard_bytes = z_standard.read('output/EC_001.json')
submit_bytes = z_submit.read('output/EC_001.json')

if standard_bytes == submit_bytes:
    print("   ✅ Hoàn toàn giống nhau (byte-by-byte)")
else:
    print(f"   ❌ Khác nhau!")
    print(f"   output.zip size: {len(standard_bytes)} bytes")
    print(f"   submission.zip size: {len(submit_bytes)} bytes")
    
    # Tìm vị trí khác nhau đầu tiên
    for i, (b1, b2) in enumerate(zip(standard_bytes, submit_bytes)):
        if b1 != b2:
            print(f"   First diff at byte {i}:")
            print(f"      output.zip: {repr(standard_bytes[max(0,i-20):i+20])}")
            print(f"      submission.zip: {repr(submit_bytes[max(0,i-20):i+20])}")
            break

# So sánh tất cả 50 files
print(f"\n📊 So sánh tất cả 50 files:")
differences = []
for i in range(1, 51):
    fname = f"output/EC_{i:03d}.json"
    std_bytes = z_standard.read(fname)
    sub_bytes = z_submit.read(fname)
    if std_bytes != sub_bytes:
        differences.append(f"EC_{i:03d}")

if differences:
    print(f"   ❌ {len(differences)} files khác nhau: {', '.join(differences[:10])}")
    if len(differences) > 10:
        print(f"      ... và {len(differences)-10} files khác nữa")
else:
    print(f"   ✅ Tất cả 50 files GIỐNG HỆT NHAU")

print("="*80)

z_standard.close()
z_submit.close()
