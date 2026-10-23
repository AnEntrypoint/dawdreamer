# v3 faust compile memory

Route: DawDreamer libfaust 2.85.9, JIT through `llvm_dsp_factory`, one
process at a time, address space capped with `ulimit -v`, peak RSS read
from `/usr/bin/time -v`. The harness was built outside the tree.

## Measurements

| dsp | cap | peak RSS | wall | result |
| --- | --- | --- | --- | --- |
| pitchtracker_ac.dsp (3f0184ab) | 6 GB | 2,215,272 KB | 10:05 | exit 0 |
| pitchtracker_ac.dsp (934258b, ad993d0c) | 6 GB | 2,228,376 KB | 10:11 | exit 0 |
| v3.dsp (2b7a6698) | 6 GB | 4,380,032 KB | 11:29 | rc 134, aborted, no output |
| v3.dsp (2b7a6698) | 8 GB | 4,759,944 KB | 11:35 | rc 137, killed, no output |

Two v3 processes at once, at 3.5 GB each, died earlier with
`std::bad_alloc` before either finished. One process at a time is what
made the pitchtracker_ac compiles succeed.

## Conclusion

The DawDreamer route does **not** rescue v3. The shipped tracker
compiles in about 2.2 GB and finishes; v3 grows past 4.7 GB and dies on
this 8 GB box at both a 6 GB and an 8 GB address-space cap, producing
no output either time. So "compile it with DawDreamer's libfaust"
is not a fix for the v3 out-of-memory by itself.

What would be a fix, in order of cost:

1. Compile v3 on a runner with more memory (CI), not on this box.
2. Split v3's candidate ladder so no single compile holds the whole
   grid in flight.
3. Raise the cap only if the box has the RAM; on 8 GB it does not.

Anyone re-running this should expect the compile, not the render, to be
the memory peak: the render of an 8 s corpus file added seconds to a
ten-minute compile.
