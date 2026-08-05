"""
Tạo submission.zip từ output folder
"""

import zipfile
import os
from pathlib import Path

def create_submission_zip():
    """Tạo submission.zip với đúng cấu trúc"""
    
    print("="*80)
    print("📦 TẠO SUBMISSION.ZIP")
    print("="*80)
    
    output_dir = Path("output")
    zip_path = Path("submission.zip")
    
    # Xóa zip cũ nếu có
    if zip_path.exists():
        zip_path.unlink()
        print(f"\n🗑️  Đã xóa submission.zip cũ")
    
    # Lấy danh sách file JSON
    json_files = sorted([f for f in os.listdir(output_dir) if f.endswith('.json')])
    
    if len(json_files) != 50:
        print(f"\n❌ Lỗi: Có {len(json_files)} files, cần đúng 50 files")
        return False
    
    print(f"\n📂 Tìm thấy {len(json_files)} files trong output/")
    
    # Tạo zip mới
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for json_file in json_files:
            file_path = output_dir / json_file
            # Lưu với đường dẫn output/EC_XXX.json
            arcname = f"output/{json_file}"
            zipf.write(file_path, arcname)
            print(f"   ✅ {arcname}")
    
    # Kiểm tra kết quả
    print(f"\n📦 Đã tạo {zip_path}")
    print(f"   Kích thước: {zip_path.stat().st_size / 1024:.2f} KB")
    
    # Verify
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        files_in_zip = zipf.namelist()
        print(f"   Số file trong zip: {len(files_in_zip)}")
        
        # Kiểm tra cấu trúc
        all_correct = all(f.startswith("output/EC_") and f.endswith(".json") for f in files_in_zip)
        if all_correct and len(files_in_zip) == 50:
            print(f"\n✅ SUBMISSION.ZIP SẴN SÀNG NỘP BÀI!")
        else:
            print(f"\n❌ Có vấn đề với cấu trúc zip")
    
    print("="*80)
    return True

if __name__ == "__main__":
    create_submission_zip()
