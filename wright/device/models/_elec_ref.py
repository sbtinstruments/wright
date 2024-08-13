from __future__ import annotations

from functools import cached_property
from pathlib import Path
from shutil import copyfile
from typing import Any, Optional
from uuid import uuid4

import anyio

from ...model import FrozenModel
from .._device_type import DeviceType
from ._frequency_sweep import FrequencySweep
from ._signal_integrity import ELEC_RULE_SETS, ElecFeatures, ElecRuleSet

_SOURCE_DATA_FILE_NAME = "electronics_reference.json"
_ELEC_RULE_SET_FILE_NAME = "electronics_rule_set.json"
_IMAGE_FILE_NAME = "electronics_reference.png"


class ElecRef(FrozenModel):
    source_data: FrequencySweep
    rule_set: ElecRuleSet
    image_file: Optional[Path] = None

    @cached_property
    def features(self) -> ElecFeatures:
        return ElecFeatures.from_frequency_sweep(self.source_data)

    @cached_property
    def is_accepted(self) -> bool:
        return self.features.is_accepted(self.rule_set)

    @classmethod
    def from_frequency_sweep(
        cls, source_data: FrequencySweep, *, device_type: DeviceType
    ):
        # TODO: Import it from external JSON file
        rule_set = ELEC_RULE_SETS[device_type]
        return cls(source_data=source_data, rule_set=rule_set)

    @classmethod
    def load_from_dir(cls, directory: Path) -> ElecRef:
        source_data_file = directory / _SOURCE_DATA_FILE_NAME
        source_data = FrequencySweep.parse_file(source_data_file)
        rule_set_file = directory / _ELEC_RULE_SET_FILE_NAME
        rule_set = ElecRuleSet.parse_file(rule_set_file)
        image_file: Optional[Path]
        image_file = directory / _IMAGE_FILE_NAME
        if not image_file.is_file():
            image_file = None
        return cls(source_data=source_data, rule_set=rule_set, image_file=image_file)

    def save_in_dir(self, directory: Path) -> None:
        source_data_file = directory / _SOURCE_DATA_FILE_NAME
        source_data_file.write_text(self.source_data.json())
        rule_set_file = directory / _ELEC_RULE_SET_FILE_NAME
        rule_set_file.write_text(self.rule_set.json())
        if self.image_file is not None:
            copyfile(self.image_file, directory / _IMAGE_FILE_NAME)

    async def generate_image(self) -> ElecRef:
        """Return copy with an image file generated from the source data."""
        return await anyio.to_thread.run_sync(self._generate_image)

    def _generate_image(self) -> ElecRef:
        from ...plots import ElecRefPlot

        image_file_name = f"electronics-reference-{uuid4()}.png"
        image_file = Path("/tmp") / image_file_name
        plot = ElecRefPlot(self)
        plot.save(image_file)
        return self.update(image_file=image_file)

    def dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # We manually exclude `cached_property`s while we wait for `computed_property`
        # and its `exclude_computed` config option. See:
        #     https://github.com/samuelcolvin/pydantic/pull/2625
        if "exclude" not in kwargs:
            kwargs["exclude"] = {"features", "is_accepted"}
        return super().dict(*args, **kwargs)

    class Config:
        # While we wait for: https://github.com/samuelcolvin/pydantic/pull/2625
        ignored_types = (cached_property,)
