import os
import zipfile
from typing import Tuple

MAX_ZIP_SIZE_BYTES = 25 * 1024 * 1024 # 25 MB
MAX_UNCOMPRESSED_SIZE_BYTES = 100 * 1024 * 1024 # 100 MB

def is_safe_zip(zip_file: zipfile.ZipFile, target_dir: str) -> Tuple[bool, str]:
    """
    Check ZIP archive for Zip Slip (path traversal) vulnerabilities and zip bombs.
    """
    target_dir_abs = os.path.abspath(target_dir)
    total_uncompressed_size = 0

    for member in zip_file.infolist():
        # Prevent Path Traversal
        filename = member.filename
        if filename.startswith("/") or filename.startswith("\\") or ".." in filename:
            return False, f"Malicious path traversal detected in ZIP entry: {filename}"

        target_path = os.path.abspath(os.path.join(target_dir_abs, filename))
        if not target_path.startswith(target_dir_abs):
            return False, f"Unsafe file path outside target directory: {filename}"

        total_uncompressed_size += member.file_size
        if total_uncompressed_size > MAX_UNCOMPRESSED_SIZE_BYTES:
            return False, "ZIP archive uncompressed size exceeds maximum allowed size (100MB)."

    return True, ""
