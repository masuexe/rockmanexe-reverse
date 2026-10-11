# Initial audit of ROMs and reference projects

Audit date: 2026-10-10. Full fingerprints are recorded in `rom-manifest.json`.

## Verified findings

`roms/` contains four ROMs: exe6f, exe6g, bn6f, and bn6g. All are 8 MiB,
pass the GBA header checksum, and have header revision 0.
There are also bn6g.sav and exe6g.sav files, both 32 KiB; their validity has not been tested.

- exe6f.gba: BR6J; its SHA-1 matches the [exe6f README](https://github.com/dism-exe/exe6f).
- bn6f.gba: BR6E; its SHA-1 matches the [bn6f README](https://github.com/dism-exe/bn6f).
- The two Gregar ROMs have not yet been checked against external baselines.

The user confirmed that all four ROMs were extracted from Legacy Collection; the extraction process was not independently verified.

## Reference project status

The user cloned both repositories locally. Both working trees were clean at the time of this audit. Pinned reference commits:

- exe6f: `fcdbb4734c1aca27c703a4af095a3ba7f4824798`
- bn6f: `d57c1968d27452de1042eff78b5dfbf124922666`

The exe6f file asm/_link.s explicitly lists assembly covering [0x08000000, 0x080005AC)
and includes bin/tail.bin at the end. Local byte comparisons confirmed that bin/exe6f.bin
matches the user's exe6f.gba exactly, and bin/tail.bin matches the ROM suffix beginning
at file offset 0x5AC. The Japanese reference project therefore mainly provides startup
and main-loop assembly; it is not a complete collection of battle functions.

The [exe6f installation instructions](https://github.com/dism-exe/exe6f/blob/master/INSTALL.md)
describe a build that overlays assembled objects onto a baseline ROM. Matching output hashes
therefore do not prove that the entire ROM has been disassembled.
The [Makefile](https://github.com/dism-exe/exe6f/blob/master/Makefile) references rom.o;
its preparation still needs to be checked against the source.

The [bn6f installation instructions](https://github.com/dism-exe/bn6f/blob/master/INSTALL.md)
involve agbcc, gbagfx, asset generation, and checksum verification. A local build has not been verified.

## Environment and proposed next step at the initial audit

The PATH contained git, make, gcc, g++, Java, Node, and npm.
It did not contain arm-none-eabi-as, arm-none-eabi-ld, a Ghidra launcher, or mGBA.
They could still have been installed elsewhere or on Windows. No dependencies were installed
and no global configuration was changed during the initial audit.

The proposed first target was the exe6f.gba input-update function at 0x080003E4,
to validate Ghidra Thumb imports and mGBA breakpoints.
See [input-update research](../research/exe6f-input-update.md) for its static analysis.
The complete reference project has not been built. REA integration was to be evaluated
on this basis. English-version symbol addresses cannot be applied directly to the Japanese ROM.

## Follow-up verification and local paths

Later on 2026-10-10, standard Ghidra 12.1.4 and mGBA 0.10.2 ran successfully.
The first candidate function was disassembled and decompiled in Thumb mode, and checked
against 53 runtime samples; see the research record for details.
The environment section above preserves the initial audit state. Current tools are located
through `scripts/tool-env.sh`.

The `roms/` and `references/` paths in this document are relative to `EXE_REVERSE_LOCAL_DIR`,
rather than the main project root. See `scripts/tool-env.sh` for the default location.
