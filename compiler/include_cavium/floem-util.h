#ifndef FLOEM_UTIL_H
#define FLOEM_UTIL_H

#include "cvmcs-nic.h"
#include <cvmx-atomic.h>

#define DMA_CACHE
#define RUNTIME  
#define RUNTIME_CORES 1
#define RUNTIME_START_CORE (12-RUNTIME_CORES)

typedef cvmx_spinlock_t lock_t;
#define qlock_init(x) cvmx_spinlock_init(x)
#define qlock_lock(x) cvmx_spinlock_lock(x)
#define qlock_unlock(x) cvmx_spinlock_unlock(x)

typedef cvmx_spinlock_t spinlock_t;
#define spinlock_init(x) cvmx_spinlock_init(x)
#define spinlock_lock(x) cvmx_spinlock_lock(x)
#define spinlock_trylock(x) cvmx_spinlock_trylock(x)
#define spinlock_unlock(x) cvmx_spinlock_unlock(x)
#define spinlock_locked(x) cvmx_spinlock_locked(x)

#define __sync_fetch_and_add32(ptr, inc) cvmx_atomic_fetch_and_add32(ptr, inc)
#define __sync_fetch_and_add64(ptr, inc) cvmx_atomic_fetch_and_add64(ptr, inc)
#define __sync_fetch_and_sub32(ptr, inc) cvmx_atomic_fetch_and_add32(ptr, -(inc))
#define __sync_fetch_and_sub64(ptr, inc) cvmx_atomic_fetch_and_add64(ptr, -(inc))
#define __sync_bool_compare_and_swap32(ptr, old, new) cvmx_atomic_compare_and_store32(ptr, old, new)
#define __sync_bool_compare_and_swap64(ptr, old, new) cvmx_atomic_compare_and_store64(ptr, old, new)

#define __SYNC CVMX_SYNCWS

unsigned long long core_time_now_ns();
uint64_t core_time_now_us();
inline uint16_t nic_htons(uint16_t x);
inline uint16_t nic_ntohs(uint16_t x);
inline uint32_t nic_htonl(uint32_t x);
inline uint32_t nic_ntohl(uint32_t x);
inline uint64_t nic_htonp(uint64_t x);
inline uint64_t nic_ntohp(uint64_t x);
#define htonp(x) x
#define ntohp(x) x
int network_send(size_t len, uint8_t *pkt_ptr, int sending_port);

#define ALIGNMENT 128
#define MEM_SIZE 1024*1024*1024

void  shared_mm_init();
void* shared_mm_malloc(int size);
void* shared_mm_memalign(int size, int alignment);
void* shared_mm_realloc(void *ptr, int size);
void  shared_mm_free(void *ptr);

#endif
