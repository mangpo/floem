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

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
} circular_queue;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    lock_t lock;
} circular_queue_lock;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    size_t clean;
} circular_queue_scan;

typedef struct {
    size_t len;
    size_t offset;
    void* queue;
    lock_t lock;
    size_t clean;
} circular_queue_lock_scan;

typedef struct {
    uint16_t flags;
    uint16_t len;
} __attribute__((packed)) q_entry;

typedef struct {
    q_entry* entry;
    uintptr_t addr;
} q_buffer;


inline void qlock_init(lock_t* lock);
inline void qlock_lock(lock_t* lock);
inline void qlock_unlock(lock_t* lock);

q_buffer enqueue_alloc(circular_queue* q, size_t len);
void enqueue_submit(q_buffer buf);
q_buffer dequeue_get(circular_queue* q);
void dequeue_release(q_buffer buf);
q_buffer next_clean(circular_queue_scan* q);
void clean_release(q_buffer buf);
#endif
