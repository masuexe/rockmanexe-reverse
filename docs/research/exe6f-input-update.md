# First validation target: input update

Status as of 2026-10-10: Ghidra Thumb disassembly, decompilation, and mGBA runtime comparison completed.
All 53 executions matched the semantic model byte for byte. Reassembly has not been tested.

## Baseline and evidence

- ROM: roms/exe6f.gba, SHA-1 d1ce0ecc8e241a716274b9fb1b6eb07fb42dd166.
- Entry: 0x080003E4, Thumb; file offset 0x3E4.
- Instruction range: [0x080003E4, 0x0800044A), followed by alignment and two literals.
- Checked range: [0x080003E4, 0x08000454), 112 bytes.
- Range SHA-256: 7c576fbb612a707b74ceb1d7c2715e464315adcb3685fbd3600be70c6b7767a3.
- This range is identical across all four local ROMs; this finding does not extend to other functions.
- Japanese source: main_static_80003E4 in references/exe6f/asm/main.s.
- English source: the function with the same name in references/bn6f/asm/main.s.
- Reference commits: see [baseline audit](../context/baseline-audit.md).

## Initial interpretation from assembly

The function obtains the input-structure pointer from field +4 of the Toolkit pointed to by r10.
It reads a halfword at 0x04000130, complements it, and stores the result at structure offset +0.
The previous state is stored at +6. Newly pressed bits are computed as current & ~previous and written to +2.
For each of the low ten bits, current & previous identifies a continuously held button;
its counter is located at +8 through +0x11.
The counter resets on release or first press, increments while continuously held, and saturates at 0x10.
The counter at +0x13 cycles from 0 to 4, controlling repeat events after saturation.
Field +4 stores filtered held-button events, distinct from the newly pressed events at +2.

The source loads 0x3FF but immediately overwrites that register without applying the mask before storing the state.
A semantic reconstruction must not add current &= 0x3FF and claim complete equivalence.

The comments in references/exe6f/structs/Toolkit/Joystick.h were treated as reference material:
the +4 comment differs from the assembly-derived interpretation, and the R/L labels at +0x10/+0x11
initially required verification. Field names needed confirmation from instructions and runtime observations,
rather than direct adoption from the reference structure. The results below resolve these points.

## Validation procedure performed

1. Map the ROM at 0x08000000, explicitly set Thumb state at the entry, and inspect control flow and literal boundaries.
2. Read r10 and *(r10+4) at the emulator entry breakpoint; inspect structure writes before return.
3. Record sequences with no buttons, first press, sustained hold, release, and two-button input.
4. Compare +0, +2, +4, +6, all ten counters, and +0x13, then implement a testable semantic model.

This function validates the tooling workflow. Attack, damage, and PvP research require separate targets.

## Ghidra results

Ghidra 12.1.4, language `ARM:LE:32:v4t:default`, Raw Binary import.
Both the program image base and the ROM block start are `0x08000000`; the block ends at `0x087FFFFF`.
Whole-ROM automatic analysis was disabled. Only the candidate function was disassembled with `TMode=1`.
Its body is `[0x080003E4, 0x0800044A)`, ending with `mov pc,lr`.
`0x0800044A..0x0800044B` is alignment; `0x0800044C` and `0x08000450` hold
`0x04000130` and `0x000003FF`, respectively. These literals were not misidentified as code.

Decompilation succeeded and its control flow agreed with the reference assembly.
The output still uses unnamed locals and `unaff_r10`, reflecting the Toolkit register convention.
The generated C was not treated as a final structure definition.
Analysis script: `scripts/ghidra/ValidateInputUpdate.java`.

In this import, Raw Binary's `-loader-baseAddr` set only the memory block address;
the image-base metadata remained zero. The script normalizes the block before setting the image base,
and checks both final values.
The global installation's headless launcher and decompiler lacked executable permissions,
so validation used a tool copy in `/tmp`, with Ghidra configuration and caches also redirected to `/tmp`.

## mGBA results

mGBA SDL 0.10.2, built-in BIOS, booting a ROM copy without a personal save.
A test SDL event source injected buttons through `LD_PRELOAD`; neither game code nor the input structure was patched.
SDL events for multiple buttons can arrive across updates, so samples are labeled by the input actually read by the CPU.
The run covered holding A+B together, but did not verify both buttons being newly pressed in the same update.

- Entry breakpoint: `0x080003E4`; `r10=0x020093B0`.
- `*(r10+4)=0x0200A270`, the input-structure address in this run.
- Input sampling breakpoint: `0x080003F8`; `r4` contains the actual result of the preceding `ldrh`.
- Before-return breakpoint: `0x08000448`, after all structure writes by this function.
- Each comparison covers the first 20 structure bytes, including every written field and the unchanged byte at `+0x12`.
- 53/53 comparisons matched, covering no input, first press and sustained hold of A, release, A+B held together, R, and L.

During input changes, the debugger command `r/2 0x04000130` can return a cached value
that lags behind the CPU's actual read. It cannot serve as the sole input evidence for that execution.
An initial mismatch prompted the additional sampling breakpoint. Final comparisons use the actual `ldrh` result,
while snapshots also retain the debugger-read value.

The field interpretations are now:

| Offset | Meaning | Runtime observations |
|---|---|---|
| `+0x00` | Current state, low 16 bits of `~KEYINPUT` | No input is `0xFC00`; no ten-bit mask is applied |
| `+0x02` | Newly pressed, `current & ~previous` | First cold-boot update is `0xFC00`; later no-input updates are zero |
| `+0x04` | Filtered held-button events | Stable no-input state retains `0xFC00`; only the low ten bits represent buttons |
| `+0x06` | Previous current state | Still `0xFC01` when A is released; returns to `0xFC00` on the next update |
| `+0x08..+0x11` | Continuous-hold counters for A, B, Select, Start, Right, Left, Up, Down, R, L | A, B, R, L verified dynamically; the remaining order follows the instruction-level bit traversal |
| `+0x12` | Byte not written by this function | Unchanged across all 53 executions |
| `+0x13` | Global repeat phase, cycling through `0..4` | Incremented at each call, reset to zero when greater than four |

R uses bit `0x0100` and counter `+0x10`; L uses bit `0x0200` and counter `+0x11`.
The two counter labels in the reference `Joystick.h` are reversed. This research uses the corrected interpretation;
the reference repository was not modified.

A sustained-hold trace (event columns show only the low ten bits):

| Sample index | A counter | Phase | Newly pressed | Held event |
|---|---:|---:|---:|---:|
| 3, first press | 0 | 4 | `1` | `0` |
| 4, still held at second sample | 1 | 0 | `0` | `1` |
| 5 | 2 | 1 | `0` | `0` |
| 19, counter reaches limit | 16 | 0 | `0` | `0` |
| 20, saturated branch entered | 16 | 1 | `0` | `0` |
| 24 | 16 | 0 | `0` | `1` |
| 29, release | 0 | 0 | `0` | `0` |

Events at `+4` therefore do not simply indicate state changes. An event occurs when the continuous-hold
counter becomes one. Counters two through sixteen produce no event; later, the saturated branch emits
an event only when the global phase is zero. The update that first reaches sixteen still takes the increment
branch and produces no event even if the phase is zero. Repeat onset also depends on the global phase;
this is not an independent five-frame timer for each button.

## Semantic model and reproduction

The `model()` function in `scripts/validate-input-update.py` returns the updated 20-byte structure,
preserving high bits and modeling counters and repeat phase. The script compiles `scripts/mgba-input-events.c`,
drives three breakpoints in standard mGBA, and compares the model output against each actual execution.
It also requires coverage of saturated A-repeat events, suppressed saturated updates, and R/L counters,
so a run containing only no-input samples cannot pass.

Run from the main project root; the work directory must not already exist:

```bash
python3 scripts/validate-input-update.py --work-dir /tmp/exe6f-input-check
```

Dependencies: Python 3, a C compiler, SDL2 development headers, and standard mGBA SDL;
all were tested locally. The ROM copy, test save, input-event library, and logs are written only to
the specified work directory. Personal saves remain unchanged.
The script currently targets the verified Japanese Falzar fingerprint and the observed Toolkit addresses;
it cannot be applied directly to other versions.

Static-analysis reproduction parameters (the installation must have the required executable permissions):

```bash
source scripts/tool-env.sh
mkdir -p /tmp/exe6f-static-projects
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
  /tmp/exe6f-static-projects input-check \
  -import "$EXE_REVERSE_LOCAL_DIR/roms/exe6f.gba" \
  -loader BinaryLoader -loader-baseAddr 0x08000000 \
  -processor ARM:LE:32:v4t -cspec default -noanalysis \
  -scriptPath "$PWD/scripts/ghidra" \
  -postScript ValidateInputUpdate.java /tmp/exe6f-static-report.txt
```

## Archived evidence and scope

Paths below are relative to `EXE_REVERSE_LOCAL_DIR`:

- Ghidra project: `ghidra-projects/input-validation-v2.gpr` and its matching `.rep/` directory.
- Final raw records: `runs/2026-10-10-input-update/`, containing `debugger.txt`, `snapshots.json`,
  `ghidra-input-update-v2.txt`, and `ghidra-v2.log`.
- `snapshots.json` SHA-256: `30e7aed28fabd6a1fa6ba0e98c97b1ddf4495a2370e2be1d95efa05a9d10d2f9`.
- Static report SHA-256: `bbbdd097b687e3af76950c4eeb69eea8cbab10c4f2a81d7f13866707b453e74f`.

These results support the interpretation of this function during startup and for the tested input sequences.
The other six individual buttons, battle and online states, abnormal structure values, reassembly,
and a complete game build remain unverified.
REA tools were unavailable in this session; validation used Ghidra headless and mGBA directly.

The next proposed step was to locate battle-state consumers of `+0`, `+2`, and `+4`,
trace B input into normal firing and charging, then investigate attack entities and damage handling.
English reference symbols require fresh matching of Japanese function addresses and bytes;
English addresses cannot be reused directly.

Follow-up: B input, charging, and attack-object creation have now been traced in the
[battle Buster research](exe6f-battle-buster.md).
The battle side recomputes press/release events from transported input buffers;
it does not directly use the global `+4` repeat-event field.

## Local paths

The `roms/` and `references/` paths in this document are relative to `EXE_REVERSE_LOCAL_DIR`,
rather than the main project root. See `scripts/tool-env.sh` for the default location.
