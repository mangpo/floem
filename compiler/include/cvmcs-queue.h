#ifndef QUEUE_H
#define QUEUE_H

#include <cvmx-atomic.h>
#include "cvmcs-nic.h"

#define ALIGN 8U
#define FLAG_OWN 1
#define TYPE_NOP 0
#define TYPE_SHIFT 8
#define TYPE_MASK  0xFF00

typedef cvmx_spinlock_t lock_t;
#define qlock_init(x) cvmx_spinlock_init(x)
#define qlock_lock(x) cvmx_spinlock_lock(x)
#define qlock_unlock(x) cvmx_spinlock_unlock(x)

typedef cvmx_spinlock_t spinlock_t;
#define spinlock_init(x) cvmx_spinlock_init(x)
#define spinlock_lock(x) cvmx_spinlock_lock(x)
#define spinlock_unlock(x) cvmx_spinlock_unlock(x)

#define __sync_fetch_and_add32(ptr, inc) cvmx_atomic_fetch_and_add32(ptr, inc)
#define __sync_fetch_and_add64(ptr, inc) cvmx_atomic_fetch_and_add64(ptr, inc)

unsigned long long core_time_now_ns();
uint64_t core_time_now_us();

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    size_t clean;
} circular_queue;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    size_t clean;
    lock_t lock;
} circular_queue_lock;

typedef struct {
    uint16_t flags;
    uint16_t len;
} __attribute__((packed)) q_entry;

typedef struct {
    q_entry* entry;
    uintptr_t addr;
} q_buffer;

q_buffer enqueue_alloc(circular_queue* q, size_t len);
void enqueue_submit(q_buffer buf);
q_buffer dequeue_get(circular_queue* q);
void dequeue_release(q_buffer buf, uint8_t flag_clean);
#endif
