"""
So sánh cấu trúc output.zip và submission.zip
"""

import zipfile

print("="*80)
print("🔍 SO SÁNH OUTPUT.ZIP vs SUBMISSION.ZIP")
print("="*80)

# Kiểm tra output.zip
print("\n📦 OUTPUT.ZIP:")
with zipfile.ZipFile('output.zip', 'r') as z:
    output_files = z.namelist()
    print(f"   Total entries: {len(output_files)}")
    print(f"   First 5:")
    for f in output_files[:5]:
        info = z.getinfo(f)
        print(f"      {f} (dir={f.endswith('/')})")

# Kiểm tra submission.zip
print("\n📦 SUBMISSION.ZIP:")
with zipfile.ZipFile('submission.zip', 'r') as z:
    submission_files = z.namelist()
    print(f"   Total entries: {len(submission_files)}")
    print(f"   First 5:")
    for f in submission_files[:5]:
        info = z.getinfo(f)
        print(f"      {f} (dir={f.endswith('/')})")

print("\n" + "="*80)
print("🔎 PHÂN TÍCH:")
print("="*80)

output_set = set(output_files)
submission_set = set(submission_files)

diff_output = output_set - submission_set
diff_submission = submission_set - output_set

if diff_output:
    print(f"\n✅ Có trong OUTPUT.ZIP nhưng không có trong SUBMISSION.ZIP:")
    for f in sorted(diff_output):
        print(f"   - {f}")

if diff_submission:
    print(f"\n✅ Có trong SUBMISSION.ZIP nhưng không có trong OUTPUT.ZIP:")
    for f in sorted(diff_submission):
        print(f"   - {f}")

print("\n" + "="*80)
print("💡 KẾT LUẬN:")
print("="*80)

if 'output/' in output_files:
    print("\n❌ OUTPUT.ZIP có thư mục 'output/' (directory entry)")
    print("   → Có thể gây lỗi với hệ thống chấm điểm")
    print("   → Hệ thống chấm có thể đếm 51 entries thay vì 50")

if 'output/' not in submission_files:
    print("\n✅ SUBMISSION.ZIP KHÔNG có directory entry")
    print("   → Chỉ có 50 files thuần túy")
    print("   → Đúng chuẩn yêu cầu đề bài")

print("\n📌 KHUYẾN NGHỊ:")
print("   → NỘP FILE: submission.zip")
print("   → KHÔNG NỘP: output.zip")

print("="*80)
