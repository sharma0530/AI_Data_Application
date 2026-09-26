from pathlib import Path
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException


router = APIRouter(prefix="/datasets", tags=["Datasets"])


# ============================================================
# Configuration
# ============================================================

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Allowed file types
# ============================================================

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".json",
    ".parquet",
}


ALLOWED_MIME_TYPES = {
    ".csv": {
        "text/csv",
        "application/csv",
        "text/plain",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    ".json": {
        "application/json",
        "text/json",
    },
    ".parquet": {
        "application/octet-stream",
        "application/vnd.apache.parquet",
    },
}


# ============================================================
# File validation
# ============================================================

def is_allowed_file(filename: str) -> bool:
    """
    Check whether the uploaded file has an allowed extension.
    """

    extension = Path(filename).suffix.lower()

    return extension in ALLOWED_EXTENSIONS


def is_valid_mime_type(
    filename: str,
    content_type: str | None,
) -> bool:
    """
    Validate the uploaded file MIME type against its extension.
    """

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_MIME_TYPES:
        return False

    if not content_type:
        return False

    return content_type.lower() in ALLOWED_MIME_TYPES[extension]


def validate_uploaded_file(file: UploadFile) -> None:
    """
    Validate extension and MIME type.
    """

    filename = file.filename or ""
    content_type = file.content_type

    if not is_allowed_file(filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file extension.",
        )

    if not is_valid_mime_type(filename, content_type):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type.",
        )


# ============================================================
# File size validation
# ============================================================

async def check_file_size(file: UploadFile) -> int:
    """
    Check whether the uploaded file is within the maximum size.
    """

    content = await file.read()

    size = len(content)

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size exceeds the maximum limit of "
                f"{MAX_FILE_SIZE / (1024 * 1024):.0f} MB."
            ),
        )

    # Reset pointer so the file can be read again.
    await file.seek(0)

    return size


# ============================================================
# Filename helpers
# ============================================================

def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename while preserving the original name.
    """

    return f"{uuid.uuid4().hex}_{original_filename}"


def create_safe_filename(
    dataset_id: str,
    original_filename: str,
) -> str:
    """
    Create an internal filename using the dataset ID.
    """

    extension = Path(original_filename).suffix.lower()

    return f"{dataset_id}{extension}"


# ============================================================
# Save file
# ============================================================

async def save_uploaded_file(
    file: UploadFile,
    safe_filename: str,
) -> Path:
    """
    Save uploaded file to the upload directory.
    """

    file_path = UPLOAD_DIR / safe_filename

    with file_path.open("wb") as buffer:

        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    await file.seek(0)

    return file_path


# ============================================================
# Temporary in-memory metadata store
# ============================================================

datasets: dict[str, dict] = {}


# ============================================================
# Upload endpoint
# ============================================================

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
):
    """
    Upload and validate a dataset.
    """

    # --------------------------------------------------------
    # 1. Validate extension + MIME type
    # --------------------------------------------------------

    validate_uploaded_file(file)

    filename = file.filename or ""

    # --------------------------------------------------------
    # 2. Check file size
    # --------------------------------------------------------

    file_size = await check_file_size(file)

    # --------------------------------------------------------
    # 3. Generate dataset ID
    # --------------------------------------------------------

    dataset_id = uuid.uuid4().hex

    # --------------------------------------------------------
    # 4. Create safe internal filename
    # --------------------------------------------------------

    safe_filename = create_safe_filename(
        dataset_id,
        filename,
    )

    # --------------------------------------------------------
    # 5. Save file
    # --------------------------------------------------------

    file_path = await save_uploaded_file(
        file,
        safe_filename,
    )

    # --------------------------------------------------------
    # 6. Create metadata
    # --------------------------------------------------------

    extension = Path(filename).suffix.lower()

    metadata = {
        "dataset_id": dataset_id,
        "filename": filename,
        "file_type": extension.replace(".", ""),
        "size_bytes": file_size,
        "stored_filename": safe_filename,
    }

    # --------------------------------------------------------
    # 7. Store metadata
    # --------------------------------------------------------

    datasets[dataset_id] = metadata

    # --------------------------------------------------------
    # 8. Return response
    # --------------------------------------------------------

    return metadata


# ============================================================
# Get dataset metadata
# ============================================================

@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
):
    """
    Get metadata for a previously uploaded dataset.
    """

    dataset = datasets.get(dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    return dataset