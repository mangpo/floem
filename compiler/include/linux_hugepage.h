#ifndef LINUX_HUGEPAGE_H
#define LINUX_HUGEPAGE_H

#define _LARGEFILE64_SOURCE
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdbool.h>

#include <linux_hugepage.h>

#define HUGE_PGSIZE (2 * 1024 * 1024)

/** Resolve virtual address into physical address */
static bool huge_virt_to_phys(void *addr, uint64_t *phys)
{
    int fd;
    bool success = true;
    uint64_t val;
    size_t page_size;
    off64_t off;

    if ((fd = open("/proc/self/pagemap", O_RDONLY)) < 0) {
        fprintf(stderr, "page_virt_to_phys: opening pagemap failed\n");
        return false;
    }

    page_size = getpagesize();
    off = (uintptr_t) addr / page_size * 8;
    if (lseek64(fd, off, SEEK_SET) != off) {
        fprintf(stderr, "page_virt_to_phys: lseek failed\n");
        success = false;
    }

    if (success && read(fd, &val, sizeof(val)) != sizeof(val)) {
        fprintf(stderr, "page_virt_to_phys: read failed\n");
        success = false;
    }
    close(fd);

    if (success) {
        /* See: https://www.kernel.org/doc/Documentation/vm/pagemap.txt
         *
         * Bits 0-54  page frame number (PFN) if present
         * Bits 0-4   swap type if swapped
         * Bits 5-54  swap offset if swapped
         * Bit  55    pte is soft-dirty (see Documentation/vm/soft-dirty.txt)
         * Bits 56-60 zero
         * Bit  61    page is file-page or shared-anon
         * Bit  62    page swapped
         * Bit  63    page present
         */
        if ((val & (1ULL << 63)) == 0 || (val & (1ULL << 62)) == 1) {
            fprintf(stderr, "page_virt_to_phys: read failed\n");
            success = false;
        } else {
            *phys = (val & ~(-1ULL << 55)) * page_size +
                    (uintptr_t) addr % page_size;
        }
    }

    return success;
}

/** Allocate a huge page (pinned), and return its virt/phys address and size */
static bool huge_alloc_phys(void **virt, uint64_t *phys, size_t *size)
{
    void *map;

    map = mmap(NULL, HUGE_PGSIZE, PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB | MAP_LOCKED,
                    -1, 0);
    if (map == MAP_FAILED) {
        fprintf(stderr, "huge_alloc_phys: mmap failed (%s)\n", strerror(errno));
        return false;
    }


    if (!huge_virt_to_phys(map, phys)) {
        fprintf(stderr, "huge_alloc_phys: finding physical address failed\n");
        munmap(map, HUGE_PGSIZE);
        return false;
    }

    *virt = map;
    *size = HUGE_PGSIZE;
    return true;
}

#endif


