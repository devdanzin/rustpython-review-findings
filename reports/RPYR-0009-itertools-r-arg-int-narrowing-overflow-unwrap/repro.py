# RPYR-0009 — itertools combinations/combinations_with_replacement/permutations
# panic on an oversized `r`. Each constructor guards `r.is_negative()` -> ValueError
# but not the too-large side, then does `to_usize().unwrap()`. A Python int is
# unbounded, so r = 2**64 makes to_usize() return None -> unwrap panics -> VM abort.
# CPython raises OverflowError: Python int too large to convert to C ssize_t.
#
# One root cause, three signatures. Run each line ALONE (a panic aborts the process).
import itertools

itertools.combinations(range(5), 2**64)                    # -> panic itertools.rs:1205
# itertools.combinations_with_replacement(range(5), 2**64) # -> panic itertools.rs:1306
# itertools.permutations(range(5), 2**64)                  # -> panic itertools.rs:1412
