"""File management utilities for project files."""

import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from config import PROJECTS_PATH


class FileManager:
    """Manages project files (images, CAD files, etc.)."""

    # Supported file extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    CAD_EXTENSIONS = {'.step', '.stp', '.iges', '.igs', '.stl', '.obj', '.3mf', '.x_t', '.x_b'}

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize file manager.

        Args:
            base_path: Base path for project storage. Defaults to PROJECTS_PATH.
        """
        self.base_path = Path(base_path) if base_path else PROJECTS_PATH
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_rfq_folder(self, rfq_id: int) -> Path:
        """Get or create folder for an RFQ.

        Args:
            rfq_id: RFQ database ID

        Returns:
            Path to RFQ folder
        """
        folder = self.base_path / f"rfq_{rfq_id:05d}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def get_part_folder(self, rfq_id: int, part_id: int) -> Path:
        """Get or create folder for a part within an RFQ.

        Args:
            rfq_id: RFQ database ID
            part_id: Part database ID

        Returns:
            Path to part folder
        """
        folder = self.get_rfq_folder(rfq_id) / f"part_{part_id:05d}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def copy_file_to_project(
        self,
        source_path: str | Path,
        rfq_id: int,
        part_id: int,
        file_type: str = 'image'  # 'image' or 'cad'
    ) -> Optional[str]:
        """Copy a file to the project folder.

        Args:
            source_path: Path to source file
            rfq_id: RFQ database ID
            part_id: Part database ID
            file_type: Type of file ('image' or 'cad')

        Returns:
            Relative path to copied file (relative to PROJECTS_PATH), or None on failure
        """
        source = Path(source_path)
        if not source.exists():
            return None

        part_folder = self.get_part_folder(rfq_id, part_id)

        # Create subfolder based on type
        if file_type == 'image':
            dest_folder = part_folder / 'images'
        elif file_type == 'cad':
            dest_folder = part_folder / 'cad'
        else:
            dest_folder = part_folder / 'other'

        dest_folder.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest_name = f"{timestamp}_{source.name}"
        dest_path = dest_folder / dest_name

        # Copy file
        try:
            shutil.copy2(source, dest_path)
            # Return path relative to base
            return str(dest_path.relative_to(self.base_path))
        except Exception:
            return None

    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path to absolute path.

        Args:
            relative_path: Path relative to PROJECTS_PATH

        Returns:
            Absolute path
        """
        return self.base_path / relative_path

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists.

        Args:
            relative_path: Path relative to PROJECTS_PATH

        Returns:
            True if file exists
        """
        return self.get_absolute_path(relative_path).exists()

    def delete_file(self, relative_path: str) -> bool:
        """Delete a file.

        Args:
            relative_path: Path relative to PROJECTS_PATH

        Returns:
            True if file was deleted
        """
        path = self.get_absolute_path(relative_path)
        try:
            if path.exists():
                path.unlink()
                return True
        except Exception:
            pass
        return False

    def delete_rfq_folder(self, rfq_id: int) -> bool:
        """Delete entire RFQ folder and contents.

        Args:
            rfq_id: RFQ database ID

        Returns:
            True if folder was deleted
        """
        folder = self.base_path / f"rfq_{rfq_id:05d}"
        try:
            if folder.exists():
                shutil.rmtree(folder)
                return True
        except Exception:
            pass
        return False

    def is_image(self, file_path: str | Path) -> bool:
        """Check if file is an image based on extension.

        Args:
            file_path: Path to file

        Returns:
            True if file has image extension
        """
        return Path(file_path).suffix.lower() in self.IMAGE_EXTENSIONS

    def is_cad(self, file_path: str | Path) -> bool:
        """Check if file is a CAD file based on extension.

        Args:
            file_path: Path to file

        Returns:
            True if file has CAD extension
        """
        return Path(file_path).suffix.lower() in self.CAD_EXTENSIONS

    def get_file_type(self, file_path: str | Path) -> str:
        """Determine file type based on extension.

        Args:
            file_path: Path to file

        Returns:
            'image', 'cad', or 'other'
        """
        if self.is_image(file_path):
            return 'image'
        elif self.is_cad(file_path):
            return 'cad'
        return 'other'


# Singleton instance
_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    """Get the singleton FileManager instance."""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
    return _file_manager
