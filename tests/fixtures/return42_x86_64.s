// Own inspection fixture. Linked with LC_UNIXTHREAD and no libc imports.
// Phase 0 never executes it; a future loader must provide the return convention.
.text
.globl _main
.p2align 4
_main:
    movl $42, %eax
    retq
