// Native ARM64 JIT substrate experiment. No x86 decoder or translator is involved.
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <libkern/OSCacheControl.h>
#include <os/arch/arm64.h>
#include <pthread.h>
#include <sys/mman.h>
#include <sys/sysctl.h>
#include <unistd.h>

#if !defined(__APPLE__) || !defined(__aarch64__)
#error This experiment must compile for native Apple Silicon.
#endif

int main() {
    int translated = 0;
    size_t translated_size = sizeof(translated);
    const int query = sysctlbyname("sysctl.proc_translated", &translated, &translated_size, nullptr, 0);
    if (query != 0 && errno != ENOENT) {
        std::perror("sysctl.proc_translated");
        return 1;
    }
    if (translated != 0) {
        std::fputs("probe must run natively\n", stderr);
        return 1;
    }
    const long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) {
        std::fputs("invalid host page size\n", stderr);
        return 1;
    }
    const bool write_protection = pthread_jit_write_protect_supported_np() != 0;
    if (!write_protection) {
        std::fputs("per-thread JIT write protection is unavailable\n", stderr);
        return 1;
    }
    void* code = mmap(nullptr, static_cast<size_t>(page_size), PROT_READ | PROT_WRITE | PROT_EXEC,
                      MAP_PRIVATE | MAP_ANON | MAP_JIT, -1, 0);
    if (code == MAP_FAILED) {
        std::perror("mmap MAP_JIT");
        return 1;
    }
    int results[2]{};
    const uint32_t immediates[] = {42, 7};
    for (int i = 0; i < 2; ++i) {
        // movz w0, #immediate; ret
        const uint32_t instructions[] = {0x52800000u | (immediates[i] << 5), 0xd65f03c0u};
        pthread_jit_write_protect_np(0);
        std::memcpy(code, instructions, sizeof(instructions));
        pthread_jit_write_protect_np(1);
        sys_icache_invalidate(code, sizeof(instructions));
        results[i] = reinterpret_cast<int (*)()>(code)();
    }
    if (munmap(code, static_cast<size_t>(page_size)) != 0) {
        std::perror("munmap");
        return 1;
    }
    bool cross_arch = false;
    if (__builtin_available(macOS 26.6, *)) {
        cross_arch = os_cross_arch_is_supported(OS_CROSS_ARCH_X86_64);
    }
    std::printf("{\"architecture\":\"arm64\",\"translated\":false,\"host_page_size\":%ld,"
                "\"jit_write_protection\":true,\"cross_arch_kernel_support\":%s,\"jit_returns\":[%d,%d]}\n",
                page_size, cross_arch ? "true" : "false", results[0], results[1]);
    return results[0] == 42 && results[1] == 7 ? 0 : 1;
}
