import os
import io
import shutil
import zipfile
import logging
from typing import Tuple
from app.uploads.security import is_safe_zip, MAX_ZIP_SIZE_BYTES

logger = logging.getLogger("codemind.uploads.zip_handler")

def process_zip_upload(file_bytes: bytes, target_dir: str) -> Tuple[bool, str]:
    """
    Safely validate and extract uploaded ZIP bytes into target_dir.
    """
    if len(file_bytes) > MAX_ZIP_SIZE_BYTES:
        return False, "File size exceeds maximum allowed upload size (25MB)."

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            is_safe, err_msg = is_safe_zip(zf, target_dir)
            if not is_safe:
                return False, err_msg
            
            zf.extractall(target_dir)

        # Handle top-level directory nesting if ZIP contains a single folder wrapper
        extracted_items = os.listdir(target_dir)
        if len(extracted_items) == 1:
            sub_path = os.path.join(target_dir, extracted_items[0])
            if os.path.isdir(sub_path):
                for item in os.listdir(sub_path):
                    s = os.path.join(sub_path, item)
                    d = os.path.join(target_dir, item)
                    shutil.move(s, d)
                os.rmdir(sub_path)

        return True, "ZIP project extracted successfully."
    except zipfile.BadZipFile:
        return False, "Uploaded file is not a valid ZIP archive."
    except Exception as e:
        logger.error(f"Error processing ZIP upload: {e}")
        return False, f"Error processing uploaded archive: {e}"
