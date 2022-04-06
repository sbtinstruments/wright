from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from typing import Optional
from uuid import uuid4

import anyio

from ...device import DeviceType
from ...device.models import FrequencySweep
from ...model import FrozenModel
from ..plots import ElecRefPlot

_SOURCE_DATA_FILE_NAME = "electronics_reference.json"
_IMAGE_FILE_NAME = "electronics_reference.png"


class ElecRef(FrozenModel):
    source_data: FrequencySweep
    image_file: Optional[Path] = None

    @classmethod
    def load_from_dir(cls, directory: Path) -> ElecRef:
        source_data_file = directory / _SOURCE_DATA_FILE_NAME
        source_data = FrequencySweep.parse_file(source_data_file)
        image_file: Optional[Path]
        image_file = directory / _IMAGE_FILE_NAME
        if not image_file.is_file():
            image_file = None
        return cls(source_data=source_data, image_file=image_file)

    def save_in_dir(self, directory: Path) -> None:
        source_data_file = directory / _SOURCE_DATA_FILE_NAME
        source_data_file.write_text(self.source_data.json())
        if self.image_file is not None:
            copyfile(self.image_file, directory / _IMAGE_FILE_NAME)

    async def generate_image(self, *, device_type: DeviceType) -> ElecRef:
        """Return copy with an image file generated from the source data."""
        return await anyio.to_thread.run_sync(self._generate_image, device_type)

    def _generate_image(self, device_type: DeviceType) -> ElecRef:
        image_file_name = f"electronics-reference-{uuid4()}.png"
        image_file = Path("/tmp") / image_file_name
        plot = ElecRefPlot(self.source_data, device_type)
        plot.save(image_file)
        return self.update(image_file=image_file)
