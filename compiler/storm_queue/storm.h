#ifndef STORM_H
#define STORM_H

#define _GNU_SOURCE
#include <pthread.h>
#include <semaphore.h>
#include <stdbool.h>
#include <stdint.h>

// Set FLEXNIC requirement here!
#if defined(BIGFISH_FLEXNIC) || defined(BIGFISH_FLEXNIC_DPDK) || defined(BIGFISH_FLEXNIC_DPDK2)
#	define FLEXNIC
//#	define NORMAL_QUEUE
#else
#	define NORMAL_QUEUE
#endif

//#define QUEUE_STAT
#define DEBUG_MP
#define DEBUG_DCCP
//#define THREAD_AFFINITY
//#define DEBUG_PERF

#define MAX_VECTOR	5	// Max. tuple vector
#define MAX_STR		64
#define MAX_WORKERS	3
#define MAX_EXECUTORS	7
#define MAX_TASKS	100
#define MAX_ELEMS	(4 * 1024)	// Queue elements
//#define MAX_ELEMS	64	// Queue elements

struct tuple;
struct executor;

typedef void (*WorkerExecute)(const struct tuple *t, struct executor *self);
typedef void (*WorkerInit)(struct executor *self);
typedef int (*GrouperFunc)(const struct tuple *t, struct executor *self);

struct tuple {
#ifndef FLEXNIC
  int		task, fromtask;
#else
  volatile int		task, fromtask;
#endif
  uint64_t 	starttime;
  struct {
    char	str[MAX_STR];
    int		integer;
  } v[MAX_VECTOR];
};

struct executor {
  int		taskid, outtasks[MAX_TASKS];
  WorkerExecute	execute;
  WorkerInit	init;
  void		*state;
  GrouperFunc	grouper;
  bool		spout;
  size_t	outqueue_empty, outqueue_full, inqueue_empty, inqueue_full;
#ifndef FLEXNIC_EMULATION
  size_t	execute_time, numexecutes, emitted, recved, avglatency;
#else
  size_t	tuples, lasttuples, full;
  size_t	wait_inq, wait_outq, memcpy_time, batchdone_time, batch_size, batches;
  int		rx_id, workerid;
#endif
  int exe_id;
} __attribute__ ((aligned (64)));


void tuple_send(struct tuple *t, struct executor *self);

static inline uint64_t rdtsc(void)
{
    uint32_t eax, edx;
    __asm volatile ("rdtsc" : "=a" (eax), "=d" (edx));
    return ((uint64_t)edx << 32) | eax;
}

#endif
