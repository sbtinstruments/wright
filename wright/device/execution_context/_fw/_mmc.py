from dataclasses import dataclass


@dataclass(frozen=True)
class MmcPartition:
    """Partition in MMC-based storage."""

    offset: int  # [sectors]
    length: int  # [sectors]


@dataclass(frozen=True)
class Mmc:
    """MultiMediaCard storage."""

    sector_size: int = 0x200  # 512 bytes
    # 0x4B000=0x9600000/0x200 sectors (i.e., 307200=150MiB/512B).
    system0: MmcPartition = MmcPartition(0x00022, 0x4B000)
    system1: MmcPartition = MmcPartition(0x4B022, 0x4B000)
    config: MmcPartition = MmcPartition(0x96022, 0x32000)
