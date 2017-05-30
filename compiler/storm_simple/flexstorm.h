#ifndef FLEXSTORM_H
#define FLEXSTORM_H

#include "worker.h"
#include "storm.h"

static void init_memory_regions() {
}
static void finalize_memory_regions() {
}

typedef struct _inject_state { struct tuple* data[1000]; int p; } inject_state;
typedef struct _task_master { struct executor **task2executor; int **task2executorid; } task_master;
typedef struct _queue_state { int core; } queue_state;
typedef struct __rx_queue_queue { int head; int tail; int size; struct tuple* data[4096]; } _rx_queue_queue;
typedef struct __rx_queue_queues { _rx_queue_queue* cores[4]; } _rx_queue_queues;
typedef struct __tx_queue_queue { int head; int tail; int size; struct tuple* data[4096]; } _tx_queue_queue;
typedef struct __tx_queue_queues { _tx_queue_queue* cores[4]; } _tx_queue_queues;
typedef struct ___tx_queue_advance_join_buffer { size_t in_arg0;  } __tx_queue_advance_join_buffer;
void outqueue_put(struct tuple* arg0, size_t arg1);

void inqueue_advance(size_t arg0);

struct tuple* inqueue_get(size_t arg0);

void init();

void run_threads();
void kill_threads();

#endif
