"""Version Manager — anti-rollback enforcement (SWR-C-019)."""
from sim import config
from sim.nvm import NvM


class VersionError(Exception):
    pass


class VersionManager:
    """Enforces monotonic firmware version counter to prevent downgrade attacks."""

    def __init__(self, nvm: NvM) -> None:
        self._nvm = nvm

    def check_version(self, image_version: int) -> None:
        """Assert image_version is strictly greater than stored counter.

        Args:
            image_version: Version number extracted from the firmware image header.

        Raises:
            VersionError: If image_version <= stored counter.
        """
        stored = self._nvm.get_counter(config.SW_VERSION_KEY)
        if image_version <= stored:
            raise VersionError(
                f"downgrade rejected: image_version={image_version} <= stored={stored}"
            )

    def commit_version(self, image_version: int) -> None:
        """Advance the NvM version counter after a successful flash commit.

        Args:
            image_version: Version number of the newly committed image.
        """
        self._nvm.write(config.SW_VERSION_KEY, image_version)

    def get_current_version(self) -> int:
        """Return the currently stored software version.

        Returns:
            Stored version counter value.
        """
        return self._nvm.get_counter(config.SW_VERSION_KEY)
