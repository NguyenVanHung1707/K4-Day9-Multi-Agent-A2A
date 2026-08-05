"""
Kiểm tra submission.zip chi tiết
"""

import zipfile
import json

print("="*80)
print("🗜️  KIỂM TRA SUBMISSION.ZIP")
print("="*80)

try:
    z = zipfile.ZipFile('submission.zip', 'r')
    
    files = sorted(z.namelist())
    
    print(f"\n📦 Tổng số file: {len(files)}")
    print(f"\n📁 Cấu trúc:")
    for i, f in enumerate(files[:5], 1):
        print(f"   {i}. {f}")
    print(f"   ...")
    for i, f in enumerate(files[-5:], 46):
        print(f"   {i}. {f}")
    
    # Kiểm tra pattern
    print(f"\n✅ Kiểm tra pattern:")
    all_match = all(f.startswith("output/EC_") and f.endswith(".json") for f in files)
    print(f"   Tất cả file đều là output/EC_*.json: {all_match}")
    
    # Kiểm tra sequence
    expected = [f"output/EC_{i:03d}.json" for i in range(1, 51)]
    missing = set(expected) - set(files)
    extra = set(files) - set(expected)
    
    if missing:
        print(f"\n❌ Thiếu file: {missing}")
    else:
        print(f"\n✅ Không thiếu file nào")
    
    if extra:
        print(f"\n❌ File thừa: {extra}")
    else:
        print(f"\n✅ Không có file thừa")
    
    # Kiểm tra encoding và JSON validity
    print(f"\n🔍 Kiểm tra từng file trong ZIP:")
    errors = []
    for fname in files:
        try:
            content = z.read(fname)
            # Thử decode UTF-8
            text = content.decode('utf-8')
            # Thử parse JSON
            data = json.loads(text)
            # Kiểm tra case_id
            expected_id = fname.split('/')[-1].replace('.json', '')
            if data.get('case_id') != expected_id:
                errors.append(f"{fname}: case_id không khớp ({data.get('case_id')} vs {expected_id})")
        except UnicodeDecodeError:
            errors.append(f"{fname}: Lỗi encoding (không phải UTF-8)")
        except json.JSONDecodeError as e:
            errors.append(f"{fname}: Lỗi JSON - {e}")
        except Exception as e:
            errors.append(f"{fname}: Lỗi khác - {e}")
    
    if errors:
        print(f"\n❌ Có {len(errors)} lỗi:")
        for err in errors:
            print(f"   - {err}")
    else:
        print(f"   ✅ Tất cả 50 file đều OK (UTF-8, valid JSON, case_id khớp)")
    
    print("\n" + "="*80)
    
    if not missing and not extra and not errors and len(files) == 50:
        print("✅ SUBMISSION.ZIP HOÀN HẢO - SẴN SÀNG NỘP BÀI")
    else:
        print("❌ CÓ VẤN ĐỀ VỚI SUBMISSION.ZIP")
    
    print("="*80)
    
except FileNotFoundError:
    print("\n❌ Không tìm thấy file submission.zip")
except Exception as e:
    print(f"\n❌ Lỗi: {e}")
