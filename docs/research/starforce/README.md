# Star Force Custom Gauge Extraction

ROM extraction tools, reverse engineering notes, and asset layout specifications for Star Force 2 and Star Force 3 Custom Gauges.
This directory documents asset provenance, ROM resources, tile decoding, layout reconstruction, and original-game reference captures. ROMs remain local and are never bundled in this repository.

- [Star Force 2 (SF2) Tile Layout and Flow Reconstruction](starforce2-custom-gauge.md)
- [Star Force 3 (SF3) Sprite Extraction and Animation Specification](starforce3-custom-gauge.md)
- Extraction scripts:
  - `scripts/starforce/extract_starforce2_gauge.py` (SF2 loose tile decoder & frame assembler)
  - `scripts/starforce/extract_starforce3_gauge.py` (SF3 Nitro container decoder & animation extractor)
- Reference captures: [frame 0](images/original-frame0.png), [frame 1](images/original-frame1.png).

## Usage

Run the extraction tools from the repository root using standard Python 3 (no third-party dependencies required):

```bash
# Star Force 2 extraction
python3 scripts/starforce/extract_starforce2_gauge.py \
  '/path/to/1722 - Ryuusei no RockMan 2 - Berserk x Shinobi (J)(Caravan).nds'

# Star Force 3 extraction
python3 scripts/starforce/extract_starforce3_gauge.py \
  '/path/to/Ryuusei no Rockman 3 - Red Joker (Japan) (Rev 1).nds'
```

Default exports are written to `exports/starforce/sf2/` and `exports/starforce/sf3/` respectively (ignored by git). Optional arguments `--output`, `--preview`, and `--raw-output` can be used to customize output paths.
