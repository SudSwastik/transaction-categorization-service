import uuid
from dataclasses import dataclass

import boto3
import magic
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename

from app.core.config import get_settings

# Extension chosen by content-sniffed MIME type, never the client-supplied filename —
# matches the `statements.file_type` enum (pdf, xlsx, docx, jpg, jpeg, png).
ALLOWED_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class UnsupportedFileTypeError(Exception):
    def __init__(self, detected_mime: str) -> None:
        self.detected_mime = detected_mime
        super().__init__(f"Unsupported file type: {detected_mime}")


class FileTooLargeError(Exception):
    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(f"File size {size_bytes} exceeds limit of {max_bytes} bytes")


@dataclass(frozen=True, slots=True)
class SavedFile:
    key: str
    original_filename: str
    size_bytes: int
    detected_mime: str
    extension: str


class StorageService:
    """S3-compatible storage (MinIO locally, real AWS S3 in prod) behind one interface.

    Swapping backends is purely env-var driven (AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY) — this client code never changes between environments.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        max_upload_size_bytes: int,
    ) -> None:
        self._bucket = bucket
        self.max_upload_size_bytes = max_upload_size_bytes
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {"404", "NoSuchBucket"}:
                self._client.create_bucket(Bucket=self._bucket)
            else:
                raise

    def save(self, *, tenant_id: uuid.UUID, filename: str, content: bytes) -> SavedFile:
        size_bytes = len(content)
        if size_bytes > self.max_upload_size_bytes:
            raise FileTooLargeError(size_bytes, self.max_upload_size_bytes)

        detected_mime = magic.from_buffer(content, mime=True)
        extension = ALLOWED_MIME_TYPES.get(detected_mime)
        if extension is None:
            raise UnsupportedFileTypeError(detected_mime)

        safe_filename = secure_filename(filename) or f"upload.{extension}"
        key = f"{tenant_id}/{uuid.uuid4()}.{extension}"

        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=content, ContentType=detected_mime
        )

        return SavedFile(
            key=key,
            original_filename=safe_filename,
            size_bytes=size_bytes,
            detected_mime=detected_mime,
            extension=extension,
        )

    def read(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body: bytes = response["Body"].read()
        return body

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {"404", "NoSuchKey"}:
                return False
            raise


def get_storage_service() -> StorageService:
    settings = get_settings()
    return StorageService(
        bucket=settings.AWS_BUCKET,
        endpoint_url=settings.AWS_ENDPOINT_URL,
        access_key_id=settings.AWS_ACCESS_KEY_ID,
        secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region=settings.AWS_REGION,
        max_upload_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
    )
